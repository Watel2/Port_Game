# Port_Game — iOS Port & Thai Translation Mod (EN → TH)

โปรเจกต์ Xcode สำหรับทดสอบการแจกตัวรัน iOS แบบ unsigned แยกจากข้อมูลและม็อดภาษาไทย รองรับ iPhone และ iPad ตั้งแต่ iOS/iPadOS 17 ตัวอย่างในแอปแสดงข้อความพร้อมแหล่งที่มาของข้อความและฟอนต์ เพื่อให้ตรวจการ override ได้บนเครื่องจริง

โปรเจกต์นี้มีข้อความตัวอย่างที่เขียนขึ้นเอง การเล่นเกมจริงต้องเชื่อมเอนจินหรือซอร์สที่ได้รับอนุญาตให้พอร์ต และจัดทรัพยากรเป็นรูปแบบที่เอนจินนั้นอ่านได้ ไฟล์ `.nsp` ในเครื่องเป็นแพ็กเกจ Switch ระบบตัวอย่างอ่านตารางข้อความ UTF-8 แบบ JSON ตามรูปแบบด้านล่าง

## โครงสร้างไฟล์

```text
C:\Port_Game\
├── .github/workflows/build-ios.yml
├── Source/
│   ├── PortGame.xcodeproj/
│   └── PortGame/
├── Local_Assets/
│   ├── Data/
│   └── Mods/
├── Game/
├── Workspace/
├── Output_IPA/
├── .gitignore
└── README.md
```

เก็บข้อมูลเกม อัปเดต DLC ฟอนต์ ม็อด และไฟล์ build ไว้ในโฟลเดอร์ local ตามโครงสร้างนี้ `.gitignore` กัน `Local_Assets/`, `Game/`, `Workspace/` และ `Output_IPA/` ออกจาก Git

## Build unsigned IPA

1. Push `Source/`, `.github/`, `.gitignore` และ `README.md` ขึ้น repository ให้ไฟล์ workflow อยู่บน default branch
2. เปิด **Actions → Build Unsigned iOS IPA → Run workflow**
3. Workflow ใช้ `macos-15` สร้าง Release สำหรับเครื่อง iOS จริงด้วย `CODE_SIGNING_ALLOWED=NO` และแพ็กแอปใน `Payload/PortGame.app`
4. ดาวน์โหลด `PortGame-unsigned.ipa` จาก **Artifacts** ไปไว้ใน `C:\Port_Game\Output_IPA\` แล้วเซ็นด้วยช่องทางติดตั้งที่ใช้ก่อนติดตั้งบน iPhone หรือ iPad

## ติดตั้ง Data และ Mods ผ่านแอปไฟล์

1. เปิด **Port Game** ครั้งแรก แอปจะสร้าง `Data` กับ `Mods` ใน Documents
2. ไปที่ **ไฟล์ → บน iPhone/iPad ของฉัน → Port Game** แล้วคัดลอกเนื้อหาจาก `Local_Assets/Data/` ลงในโฟลเดอร์ `Data` ที่แอปสร้างไว้
3. กลับมาเปิดแอปหรือกด **โหลดไฟล์ใหม่** ในตัวอย่างที่มากับโปรเจกต์ ข้อความอังกฤษจะเปลี่ยนจาก *pier* เป็น *lighthouse* และแสดงแหล่งที่มาเป็น `Data`
4. คัดลอกเนื้อหาจาก `Local_Assets/Mods/` ลงในโฟลเดอร์ `Mods` แล้วโหลดใหม่ ข้อความจะเปลี่ยนเป็นภาษาไทยและแสดงแหล่งที่มาเป็น `Mods`
5. เมื่อต้องการย้อนกลับเป็นอังกฤษ ให้นำไฟล์คำแปลออกจาก `Mods` แล้วโหลดใหม่

## รูปแบบข้อความและฟอนต์

ไฟล์ข้อความแต่ละชั้นใช้พาธ `Localization/strings.json` แอปเลือกค่าทีละรหัสตามลำดับ `Documents/Mods/` → `Documents/Data/` → `DefaultAssets/` ใน App Bundle รหัสที่ไม่มีในม็อดหรืออยู่ในไฟล์ JSON ที่อ่านไม่ได้จะตกไปใช้ค่าจากลำดับถัดไป ตัวอย่าง `Mods/Localization/strings.json` เป็นดังนี้

```json
{
  "preview.title": "พร้อมออกสำรวจ",
  "preview.body": "หยิบแผนที่แล้วเดินตามเส้นทางไปยังประภาคาร"
}
```

- บันทึก JSON เป็น UTF-8 ใช้พาธและตัวพิมพ์ตามตัวอย่าง และคงรหัสข้อความกับตัวแปรเดิมเมื่อนำไปเชื่อมกับตารางคำแปลของเกม
- หากต้องการทดสอบฟอนต์ ให้วางฟอนต์ TrueType ที่ได้รับอนุญาตและรองรับภาษาไทยไว้ที่ `Mods/Fonts/Thai.ttf` แล้วโหลดใหม่ แอปเลือกฟอนต์ตามลำดับเดียวกับข้อมูลและใช้ฟอนต์ระบบเมื่อหาไฟล์ที่อ่านได้ไม่เจอ
- ตรวจตำแหน่งสระและวรรณยุกต์บนเครื่องจริง ถ้าเอนจินเกมจริงตัดบรรทัดภาษาไทยไม่ถูก ให้แก้ระบบตัดคำหรือแทรก Zero-Width Space (`U+200B`) เฉพาะจุดตัดคำที่จำเป็น

## แบบฝึกหัดแรกสำหรับแยก IPA, Data และม็อด

ใช้ข้อความตัวอย่างในโปรเจกต์เพื่อทดสอบตัวโหลดทีละชั้น หลังติดตั้งต้นแบบบน iPhone ให้ลองตามลำดับนี้

| ไฟล์ที่วาง | ผลที่ควรเห็น |
|---|---|
| เปิดครั้งแรกโดยยังไม่คัดลอกไฟล์ | ข้อความอังกฤษลงท้ายด้วย *pier* และแหล่งที่มาเป็น App Bundle |
| คัดลอกเฉพาะ Data | ข้อความอังกฤษลงท้ายด้วย *lighthouse* และแหล่งที่มาเป็น Data |
| เพิ่ม Mods | ข้อความเปลี่ยนเป็นไทยและแหล่งที่มาเป็น Mods |
| เอาเฉพาะรหัส `preview.body` ออกจากไฟล์ใน Mods | หัวข้อยังเป็นไทย ส่วนข้อความด้านล่างกลับมาเป็นอังกฤษจาก Data |

ใน nxnative ชั้นข้อมูลเกมเรียกว่า **RomFS** โครงการมีโหมด `--romfs separate` สำหรับเก็บไฟล์ RomFS แยกจาก IPA และให้ย้ายไฟล์ไปยังตำแหน่งที่ตัวรันกำหนด การแยก RomFS ช่วยให้เข้าใจส่วน Data แต่การโหลดแพ็กภาษาเพิ่มต้องอาศัยรูปแบบไฟล์และวิธี override ที่ตัวรันหรือเกมรองรับโดยเฉพาะ [เอกสารต้นทางของ nxnative](https://github.com/seedds/nxnative/#install)

## ตรวจความพร้อมของ nxnative

ใช้ **Actions → Check nxnative iOS build → Run workflow** เมื่อ workflow อยู่ใน default branch แล้ว งานนี้ใช้ runner `xcode-27`, เลือก Xcode 27.2 และติดตั้ง Metal Toolchain กับ XcodeGen เพื่อคอมไพล์และลิงก์แอปด้วยข้อมูลจำลองของ nxnative ผลผ่านยืนยันว่า toolchain ใช้ build แอป iOS ของ nxnative ได้ การยืนยันว่าเกมรันได้ยังต้องใช้ iPhone หรือ iPad จริง [ตัวอย่างการทดสอบของ nxnative](https://github.com/seedds/nxnative/blob/main/.github/workflows/tests.yml) · [รายการ Xcode บน runner](https://github.com/actions/runner-images/blob/main/images/macos/xcode-27-arm64-Readme.md)

สำหรับเครื่อง build ของคุณเอง nxnative รุ่นที่ตรวจระบุ Mac ชิป Apple Silicon, macOS 26.6 ขึ้นไป, Xcode 27.2 พร้อม iOS SDK และ Metal Toolchain, Python arm64 และแพ็กเกจตามคู่มือของโครงการ ถ้าจะส่ง RomFS เข้าเครื่องจริงทาง USB เครื่อง Mac ที่ต่อกับ iPhone ใช้ `libimobiledevice` ตามวิธีในคู่มือ [ข้อกำหนด nxnative](https://github.com/seedds/nxnative/#requirements) · [การติดตั้ง RomFS แยก](https://github.com/seedds/nxnative/blob/main/docs/development.md#quick-reinstalls)

เมื่อใช้โหมดแยกข้อมูล nxnative อ่านภาพข้อมูลเกมจาก `Documents/romfs.img` และตรวจว่าเป็นภาพของ build เดียวกัน เอกสารระบุ `DM_ROMFS_OVERLAY` เป็นช่องทางแทนที่ไฟล์ใน RomFS ส่วนแพ็กแปลไทยของเกมจริงต้องระบุไฟล์หรือ archive ที่มีข้อความอังกฤษและทดลองแทนที่หนึ่งรายการบนเครื่องจริงก่อน [เอกสารการโหลด RomFS](https://github.com/seedds/nxnative/blob/main/docs/development.md#quick-reinstalls)

บน Windows ลองแพ็กเฉพาะข้อมูลตัวอย่างของโปรเจกต์เพื่อศึกษารูปแบบ RomFS ได้จากรากโปรเจกต์ คำสั่งนี้ใช้ตัวแพ็กจาก nxnative ที่อยู่ใน `Workspace/nxnative` และบันทึกผลไว้ในโฟลเดอร์ local เท่านั้น

```powershell
New-Item -ItemType Directory -Force Workspace/Sample_Data | Out-Null
python Workspace/nxnative/dm/tools/romfs_image.py Local_Assets/Data Workspace/Sample_Data/romfs.img --reuse
```

สำหรับ *Digimon Story Time Stranger* โปรไฟล์ upstream ระบุ Title ID `010062E01FE0C000` และมีผลทดสอบอัปเดต 1.2.2 บน Mac ส่วนผลทดสอบ iPhone ของ 1.2.1 มาจาก build ที่ผู้ทดสอบระบุไว้ใน issue ให้เก็บเลขอัปเดตและ commit ของ nxnative ทุกครั้งที่ทดสอบเพื่อเปรียบเทียบผลได้ตรงรุ่น [โปรไฟล์เกม](https://github.com/seedds/nxnative/blob/main/dm/games/010062E01FE0C000/README.md) · [รายงานผลทดสอบ 1.2.1](https://github.com/seedds/nxnative/issues/872)
