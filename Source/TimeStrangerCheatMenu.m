#import <UIKit/UIKit.h>
#import "TimeStrangerCheatMenu.h"
#include "dm.h"
#include <limits.h>
#include <stdatomic.h>
#include <stdio.h>

enum { WalletMax = 99999999, MultiplierMax = 20 };
static _Atomic uint32_t pendingWallet = UINT32_MAX;
static _Atomic uint32_t experienceMultiplier = 1;
static _Atomic uint32_t unreportedMultiplier = 0;
static BOOL configuredMenu;

static void applyWallet(uint64_t *regs, int param) {
    if (!regs[0]) return;
    uint32_t yen = atomic_exchange(&pendingWallet, UINT32_MAX);
    if (yen == UINT32_MAX) return;
    *(uint32_t *)(uintptr_t)(regs[0] + 0x58) = yen;
    fprintf(stderr, "[cheat-menu] set wallet to %u yen\n", yen);
}

static void preserveWallet(uint64_t *regs, int param) {
    // Preserve balances explicitly raised above the regular ceiling when spending.
    if (regs[0] && *(const uint32_t *)(uintptr_t)(regs[0] + 0x58) > 9999999)
        regs[9] = WalletMax;
}

static void applyExperience(uint64_t *regs, int param) {
    uint32_t multiplier = atomic_load(&experienceMultiplier);
    uint32_t reward = (uint32_t)regs[8], accumulated = (uint32_t)regs[9];
    if (multiplier == 1 || reward == 0 || reward > INT32_MAX || accumulated > INT32_MAX) return;
    uint64_t scaled = (uint64_t)reward * multiplier;
    uint32_t available = INT32_MAX - accumulated;
    regs[8] = scaled > available ? available : scaled;
    uint32_t report = multiplier;
    if (atomic_compare_exchange_strong(&unreportedMultiplier, &report, 0))
        fprintf(stderr, "[cheat-menu] EXP x%u: %u -> %llu\n",
                multiplier, reward, (unsigned long long)regs[8]);
}

__attribute__((constructor))
static void attachCheatMenu(void) {
    gate_obs_set(27, applyWallet);
    gate_obs_set(28, preserveWallet);
    gate_obs_set(29, applyExperience);
}

static UIViewController *presenter(void) {
    for (UIScene *scene in UIApplication.sharedApplication.connectedScenes) {
        if (scene.activationState != UISceneActivationStateForegroundActive ||
            ![scene isKindOfClass:UIWindowScene.class]) continue;
        for (UIWindow *window in ((UIWindowScene *)scene).windows) {
            if (!window.isKeyWindow) continue;
            UIViewController *top = window.rootViewController;
            while (top.presentedViewController && !top.presentedViewController.isBeingDismissed)
                top = top.presentedViewController;
            return top;
        }
    }
    return nil;
}

static BOOL readInteger(NSString *input, NSInteger minimum, NSInteger maximum, NSInteger *value) {
    NSString *text = [input stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceAndNewlineCharacterSet];
    NSScanner *scanner = [NSScanner scannerWithString:text ?: @""];
    NSInteger parsed;
    if (![scanner scanInteger:&parsed] || !scanner.isAtEnd || parsed < minimum || parsed > maximum) return NO;
    *value = parsed;
    return YES;
}

static void showMenu(NSString *message, NSString *walletText, NSString *xpText) {
    UIViewController *controller = presenter();
    if (!controller) return;
    UIAlertController *alert = [UIAlertController alertControllerWithTitle:@"เงินเยนและ EXP"
        message:message preferredStyle:UIAlertControllerStyleAlert];
    [alert addTextFieldWithConfigurationHandler:^(UITextField *field) {
        field.placeholder = @"ยอดเงินเยน (เว้นว่างเพื่อข้าม)";
        field.text = walletText;
        field.keyboardType = UIKeyboardTypeNumberPad;
        field.accessibilityLabel = @"ยอดเงินเยน";
    }];
    [alert addTextFieldWithConfigurationHandler:^(UITextField *field) {
        field.placeholder = @"ตัวคูณ EXP (1–20)";
        field.text = xpText;
        field.keyboardType = UIKeyboardTypeNumberPad;
        field.accessibilityLabel = @"ตัวคูณ EXP";
    }];
    [alert addAction:[UIAlertAction actionWithTitle:@"ยกเลิก" style:UIAlertActionStyleCancel handler:nil]];
    __weak UIAlertController *weakAlert = alert;
    [alert addAction:[UIAlertAction actionWithTitle:@"ใช้งาน" style:UIAlertActionStyleDefault handler:^(__unused UIAlertAction *action) {
        NSString *yenText = weakAlert.textFields.firstObject.text;
        NSString *expText = weakAlert.textFields.lastObject.text;
        BOOL setWallet = [yenText stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceAndNewlineCharacterSet].length > 0;
        NSInteger yen, exp;
        if ((setWallet && !readInteger(yenText, 0, WalletMax, &yen)) ||
            !readInteger(expText, 1, MultiplierMax, &exp)) {
            dispatch_after(dispatch_time(DISPATCH_TIME_NOW, 400 * NSEC_PER_MSEC), dispatch_get_main_queue(), ^{
                showMenu(@"ใส่เงิน 0–99,999,999 และตัวคูณ EXP 1–20 เป็นจำนวนเต็ม", yenText, expText);
            });
            return;
        }
        if (setWallet) atomic_store(&pendingWallet, (uint32_t)yen);
        atomic_store(&unreportedMultiplier, (uint32_t)exp);
        atomic_store(&experienceMultiplier, (uint32_t)exp);
        configuredMenu = YES;
    }]];
    [controller presentViewController:alert animated:YES completion:nil];
}

void TimeStrangerShowCheatMenu(void) {
    if (!gate_obs_present(27) || !gate_obs_present(28) || !gate_obs_present(29)) return;
    uint32_t current = atomic_load(&experienceMultiplier);
    showMenu(@"ยอดใหม่มีผลเมื่อเกมอ่านกระเป๋าเงิน ตัวคูณมีผลกับ EXP ที่ได้จากการต่อสู้",
             configuredMenu ? @"" : @"99999999",
             [NSString stringWithFormat:@"%u", configuredMenu ? current : 3]);
}
