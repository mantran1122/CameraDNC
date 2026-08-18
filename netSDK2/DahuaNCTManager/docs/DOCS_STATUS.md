# Docs Status

## Purpose

File nay dung de xac dinh:

- Nen doc file nao truoc
- File nao dang la nguon tham chieu chinh
- File nao con dung nhung can doc kem canh bao
- File nao nen cap nhat tiep

## Current Summary

Tinh den luc nay:

- `05_SDK_Integration.md` la tai lieu trung tam va dang khop nhat voi huong di hien tai
- `03_Build_Guide.md` phan anh cach build workspace hien tai tot hon `00_Project_Overview.md`
- `00_Project_Overview.md` va `01_Architecture.md` van huu ich, nhung dang co loi encoding o nhieu doan tieng Viet
- `06`, `07`, `08`, `09`, `15` la nhom tai lieu ngan, dung duoc de dinh huong, nhung can viet lai hoac bo sung them

## Read First

Day la thu tu nen doc truoc moi khi tiep tuc project:

1. [00_Project_Overview.md](./00_Project_Overview.md)
   Tong quan muc tieu va pham vi du an.
   Luu y: file nay dang co loi encoding va co noi dung cu ghi `MSVC x64`.

2. [01_Architecture.md](./01_Architecture.md)
   Mo ta cac layer va vai tro cua `AppController`, manager, va wrapper SDK.
   Luu y: file nay cung dang co loi encoding o mot so doan.

3. [05_SDK_Integration.md](./05_SDK_Integration.md)
   Tai lieu quan trong nhat hien tai.
   Chot huong "boc SDK Dahua bang app Qt/C++".
   Co phase refactor va checklist thuc hien ro rang.

4. [03_Build_Guide.md](./03_Build_Guide.md)
   Cach build va chay workspace hien tai.
   Hien dang nghieng ve Qt 6.11.1 MinGW + Ninja.

5. [04_UI_Design.md](./04_UI_Design.md)
   Muc tieu giao dien va huong UX tong quan.

## Trust Level By Document

### High Trust

- [05_SDK_Integration.md](./05_SDK_Integration.md)
  Nguon tham chieu chinh cho huong wrapper SDK, preview, va download.

- [03_Build_Guide.md](./03_Build_Guide.md)
  Nen uu tien khi can build/run project trong workspace hien tai.

### Medium Trust

- [00_Project_Overview.md](./00_Project_Overview.md)
  Con dung o muc tong quan, nhung co loi encoding va mot so thong tin can doi chieu lai voi docs moi hon.

- [01_Architecture.md](./01_Architecture.md)
  Con gia tri ve mat cau truc, nhung nen doc kem `05_SDK_Integration.md`.

- [02_Project_Structure.md](./02_Project_Structure.md)
  Huu ich khi refactor, nhung co the chua theo kip trang thai code hien tai.

### Needs Refresh

- [06_Class_Design.md](./06_Class_Design.md)
- [07_API_Reference.md](./07_API_Reference.md)
- [08_Testing.md](./08_Testing.md)
- [09_Roadmap.md](./09_Roadmap.md)
- [15_Project_Checklist.md](./15_Project_Checklist.md)

Nhung file nay dung de dinh huong nhanh, khong nen xem la nguon su that cuoi cung cho implementation.

### Read Later

- [10_Coding_Standards.md](./10_Coding_Standards.md)
- [11_Class_Diagram.md](./11_Class_Diagram.md)
- [12_Sequence_Diagrams.md](./12_Sequence_Diagrams.md)
- [13_Database_Design.md](./13_Database_Design.md)
- [14_JSON_Config.md](./14_JSON_Config.md)

Chi mo som neu cong viec dang lien quan truc tiep den coding style, model hoa, luu tru, hoac config.

## Important Warnings

Can doc voi nhan xet nay de tranh bi lech huong:

- `05_SDK_Integration.md` noi ro huong dung la wrapper SDK, khong phai viet lai SDK.
- `03_Build_Guide.md` hien mo ta moi truong MinGW, trong khi `00_Project_Overview.md` van ghi `MSVC x64`.
- `00_Project_Overview.md` va `01_Architecture.md` dang bi loi encoding, nen uu tien y chinh thay vi tin tung cau chu.
- Mot so file roadmap/checklist/testing hien con qua ngan, chua phan anh day du cac buoc refactor preview va download.

## Recommended Reading Order Today

Neu bat dau lai de lam viec tiep, doc theo thu tu nay:

1. `00_Project_Overview.md`
2. `01_Architecture.md`
3. `05_SDK_Integration.md`
4. `03_Build_Guide.md`
5. `04_UI_Design.md`

## Next Suggested Doc Work

Neu tiep tuc don bo docs, nen uu tien cap nhat:

1. `00_Project_Overview.md`
   Sua loi encoding va dong bo lai thong tin compiler/build.

2. `01_Architecture.md`
   Sua loi encoding va bo sung cach tach preview host khoi SDK wrapper.

3. `06_Class_Design.md`
   Viet lai de khop voi `DahuaSdkManager`, `PreviewHost`, va multi-tile preview.

4. `09_Roadmap.md`
   Cap nhat lai theo cac phase trong `05_SDK_Integration.md`.

5. `15_Project_Checklist.md`
   Bien thanh checklist thuc chien de theo doi tien do build, login, live, download.
