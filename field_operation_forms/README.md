# Field Operation Forms

> Saha servis formu (field.operation.forms) — iş emrinden form üretimi, ekip ataması,
> müşteri/personel e-imzası, portal erişimi, kendi PDF raporu ve paylaşılan PDF başlık/altlık düzeni.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.1.0`
> Modül: `field_operation_forms` · 28 takipli dosya (11 py · 9 xml) · 1 yeni model + 2 genişletme + form denetleyicisi + 1 QWeb PDF raporu

Bu doküman modül kodundan üretilmiştir (manifest + models + controllers + views + templates +
security + data + i18n). Kanıtı olmayan iş bilgisi `<!-- DOLDURULACAK -->` ile işaretlenmiştir.

## 1. Genel Bakış

`field.operation` iş emrinden türeyen, müşteri tarafından imzalanan servis formu modelini kurar. Suite'in diğer form modülleri (dezenfeksiyon, pest vb.) bu modeli `_inherit` ile genişletir.

- `field.operation.forms` — yeni model: referans, müşteri/adres, servis tipi, durum, imza alanları
- `field.operation` üzerine **Create Form** butonu ve **Forms** sayaç kutusu
- Portal: `/my/operation_forms` listesi, detay sayfası ve iki imza ucu (müşteri + personel)
- QWeb PDF raporu: **Service Form** (`report_type=qweb-pdf`, forma "Print" olarak bağlı) — aynı
  `external_forms` başlık/altlık düzenini kullanır; bu düzeni `field_operation_disinfect` de çağırır
- E-posta şablonu **Saha Servis Formu** (form PDF'ini ek olarak taşır) + `FOF-` önekli numara serisi

Kapsam dışı: cron kurmaz, harita/WhatsApp entegrasyonu içermez (bkz. `field_operation_geolocation` ve `field_operation_whatsapp`).

<!-- DOLDURULACAK: Form "completed" durumuna hangi iş kuralıyla geçiyor (saha onayı, kontrol listesi)? -->

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `field_operation` | `field.operation`, `field.operation.type`, `field.operation.team` modelleri; inherit edilen `view_field_operation_form`; durum sabitleri (`draft/planned/progress/done/cancel`) |
| Odoo çekirdek | `mail` (`mail.thread`, `mail.activity.mixin`), `portal` (`portal.mixin`, `CustomerPortal`), `hr` (`person_ids` → `hr.employee`) |

## 3. Ana Modeller

| Model | Tür | Ana İçerik |
|---|---|---|
| `field.operation.forms` | **Yeni** (`mail.thread` + `mail.activity.mixin` + `portal.mixin`, `_order = "create_date desc"`) | `name`, `subject`, `description`, `solution`, `start_date`, `end_date`, `status`, `operation_id`, `team_id`, `team_leader_id`, `person_ids`, `customer_id`, `contact_id`, `contact_mobile` (readonly related), `address_id`, `area_id`, `company_id`, `service_type_id`, `service_type` (readonly related), imza alanları, `signed` (compute), `operation_count` |
| `field.operation` | `_inherit` | `forms_id` (Many2one), `forms_count` (compute), `show_forms()`, `action_create_forms()` |
| `res.partner` | `_inherit` | `_compute_display_name` — `contact_display='name_only'` bağlamında yalnız ad döner |

Durum seçimi: `new` → `completed` → `done`, ayrıca `cancel`. Form numarası `FOF-` önekli
`ir.sequence` (`padding=5`, `noupdate=1`) ile üretilir; `create()`, alan varsayılanı olan `/` istemciden
geri geldiğinde de seriyi atar (eskiden yalnız `name` hiç gönderilmediğinde çalışıyordu).

`signed` **türetilmiş** alandır: `customer_signature` **ve** `staff_signature` dolu ise `True`
(`_compute_signed`). Saklanmaz, dolayısıyla elle yazılamaz ve imza görüntülerinden ayrışamaz.

## 4. Roller ve Güvenlik

Kategori: `ir.module.category` → "Field Service Forms" (sequence 23).

| Grup | İçerdiği | Not |
|---|---|---|
| `forms_user` (Field User) | `base.group_user` | Saha kullanıcısı |
| `forms_all` (All Data) | `forms_user` | Tüm veriyi görür |
| `forms_manager` (Field Manager) | `forms_all` | Başlangıçta `base.user_root` ve `base.user_admin` üyeliği |

ACL (`field.operation.forms`): `forms_user` **1/1/0/0**, `forms_manager` 1/1/1/1,
`base.group_portal` **1/0/0/0** (portal salt okur; imza yazımı denetleyiciden `sudo()` ile).

| Kayıt kuralı | Grup | Domain |
|---|---|---|
| `forms_user_rule` | `forms_user` | `['&', ('status','in',('new','completed')), '\|', ('team_leader_id','=',user.id), ('person_ids.user_id','=',user.id)]` |
| `forms_all_rule` | `forms_all` | `[(1,'=',1)]` |
| `forms_manager_rule` | `forms_manager` | `[(1,'=',1)]` |
| `field_operation_forms_portal_rule` | `base.group_portal` | `['\|', ('message_partner_ids','child_of',[user.partner_id.commercial_partner_id.id]), ('customer_id','in',[user.partner_id.id])]` |
| `multi-company_form_rule` | **grup yok (global)** | `[('company_id','in',company_ids)]` |

`action_create_forms` kaydı `sudo()` ile yaratır (oluşturma hakkı `forms_manager`'da, akış ise
`forms_user` / `field_operation.service_group_*` gruplarıyla yürür) ve grubu ayrıca sunucuda kontrol eder;
`forms_user` grubunun `perm_create=0` olması saha kullanıcısının form üretmesini engellemez.

## 5. Ana Akış

Menü yolu: **Field Forms → Field Operation Form** (kök menü sequence 36, `web_icon` ikonlu).

| Adım | Kayıt | Detay |
|---|---|---|
| Kök menü | `root_menu_field_operation_forms` | grup `forms_user` |
| Liste menüsü | `menu_field_operation_forms` | `action_field_operation_forms`, sequence 2 |
| Yapılandırma | `menu_field_operation_forms_config` | grup `forms_manager`, sequence 20 (alt menüler başka modüllerden gelir, ör. `field_operation_disinfect`) |
| Aksiyon | `action_field_operation_forms` | `view_mode=list,form`, bağlam `{'search_default_new': 1, 'search_default_my_tasks': 1}` |
| PDF raporu | `action_service_form_pdf` | `qweb-pdf`, model `field.operation.forms`, `binding_type=report` → formda "Print > Service Form" |

| Form butonu | Metod | Görünürlük | Grup |
|---|---|---|---|
| Completed | `action_completed` | `status in ('completed','done','cancel')` dışında | — |
| Signature | `action_signe_form` | `signed and status in ('new','done','cancel')` dışında | — |
| Done | `action_done` | `status in ('new','done','cancel')` dışında | `forms_manager` |
| Email | `action_mail_send` | `status in ('new','completed','cancel')` dışında | `forms_manager` |
| Cancel | `action_cancel` | yalnız `status in ('completed','done')` | `forms_manager` |
| Draft | `action_draft` | yalnız `status == 'cancel'` | — |

Durum çubuğu: `statusbar_visible="new,completed,done,cancel"`, `readonly="1"`. İş emrinden üretim: **Create Form** →
`action_create_forms` (takım seçili değilse veya form zaten varsa `UserError`); buton yalnız **açık ve formsuz**
operasyonda görünür (`invisible="forms_count != 0 or status in ('draft','done','cancel')"`) →
form kaydı `sudo()` ile oluşturulur ve `operation_id` ile iş emrine bağlanır. `action_done`,
form alanlarını (imza, çözüm, tarih) `operation_id` ile bağlı **tek** `field.operation` kaydına geri yazar.

Portal: `/my/operation_forms` (sayfalama, `start_date desc` / `name desc`) →
`/my/operation_forms_detail/<id>` → imza uçları `/form/customer_sign/<source>` ve
`/form/staff_sign/<source>` (`type="jsonrpc"`, `auth="public"`, `_document_check_access` ile
token doğrulamalı).

## 6. Alan Eşlemeleri / Liste Kolonları

Liste görünümü (`field.operation.forms.list`; `status == 'done'` yeşil, `status == 'new'` sarı):

| Varsayılan görünür (`optional="show"`) | Gizli (`optional="hide"`) |
|---|---|
| `service_type`, `contact_id`, `contact_mobile`, `team_id`, `person_ids` (`many2many_tags_avatar`), `status`, `start_date`, `end_date` | `name`, `subject`, `customer_id`, `area_id`, `address_id`, `team_leader_id`, `company_id` (readonly) |

`action_create_forms` eşlemesi (kaynak → hedef): `subject`, `description`, `service_type_id`, `start_date`, `contact_id`, `address_id`, `user_id`, `team_id`, `team_leader_id`, `company_id` aynı adlarla; `partner_id` → `customer_id`; `person_ids` → `person_ids` (`Command.set`); `self.id` → `operation_id`.
`action_done` geri yazımı: `end_date`, `signed_on`, `signed_by` (`customer_signed_by`), `form_signature` (`customer_signature`), `staff_signed_by`, `staff_signature`, `solution` — operasyon kaydına `sudo()` ile, alan listesi sabittir.

Bağ tek yönlüdür: `field.operation.forms.operation_id` gerçek bağdır, `field.operation.forms_id` ondan **türetilir** (compute + store + readonly). İkisi artık ayrışamaz.

## 7. Arama Filtreleri

| Öğe | Domain / Etki |
|---|---|
| Alan "No" | `name ilike self` |
| `customer_id` alan araması | `[('customer_id','child_of', self)]` |
| `team_id`, `service_type`, `status` | Doğrudan alan araması |
| My Tasks | `team_leader_id = uid` (varsayılan açık) |
| My Task | `person_ids.user_id = uid` |
| New / Completed | `status = 'new'` / `status = 'completed'` (New varsayılan açık) |
| Team / Assigned Person | Gruplama: `team_id` / `person_ids` |

`forms_user` kayıt kuralı bu filtrelerle uyumludur: `status in ('new','completed')` **ve**
(`team_leader_id = user.id` **veya** `person_ids.user_id = user.id`). Böylece saha çalışanı kendine
atanmış işi listede görür, iş kapandığında (`done`/`cancel`) listeden çıkar.

## 8. Test Kapsamı

`tests/test_field_operation_forms.py` — 15 test (14 `TransactionCase` + 1 `HttpCase`), hepsi yeşil
(`--test-tags /field_operation_forms`, scratch DB `soft_gantt_check`):

1. Operasyon ↔ form bağının senkron kalması (taşıma, koparma, sayaçlar).
2. Butonun ikinci formu reddetmesi (mükerrer/orphan üretimi biter).
3. `action_create_forms` — takım yoksa `UserError`, yetki yoksa `AccessError`.
4. `forms_user` görünürlüğü: lider **ve** atanmış personel açık formu görür; kapanan form listeden çıkar.
5. Durum aksiyonlarında sunucu tarafı grup kontrolü (`AccessError`).
6. `action_done` sonucu operasyona yazar; bağ yoksa `UserError` (sessiz geçmez).
7. İmza zaman damgası gerçek bir `Datetime`; ad yazmak formu imzalı işaretlemez.
8. Arama görünümündeki `filter_domain`'lerin gerçek alanlara işaret etmesi.
9. Portal salt-okunur; imza yazımı beyaz liste + base64 doğrulamasıyla.
10. `HttpCase`: portal sayfası 200 döner, imza ucu `force_refresh` verir ve imzayı kaydeder.
11. İstemcinin gönderdiği `/` varsayılanıyla yaratılan form `FOF-` numarası alır.
12. `signed` iki imzadan türetilir; `write()` ile zorlanamaz.
13. `contact_mobile` okuma yönünde akar, `res.partner.phone`'u ezmez.
14. PDF raporu modele bağlı, `%PDF` üretir ve e-posta şablonu bu raporu ek olarak taşır.
15. "Create Form" butonunun görünürlük koşulu (formu olan operasyonda görünmez).
    Ayrıca `HttpCase` testi portal imza kısayollarının imza sonrası kaybolduğunu doğrular.

## 9. Geliştirici Notları

- `migrations/19.0.1.1.0/post-migrate.py`: `forms_id` türetilmiş alana dönüştüğü için, eski verilerde
  ayrışmış bağları yeniden hesaplar (canlı veride 223 operasyonun `forms_id`'si değişir: ~200 yanlış bağ
  temizlenir, ~23 eksik bağ doğru forma bağlanır). `data/forms_data.xml` `noupdate="1"` ile seriyi korur;
  seri şirkete bağlı değildir (`company_id = False`), önek `FOF-`, `padding=5`.
- E-posta şablonu `field_operation_forms_email_template` (ad: "Saha Servis Formu", `auto_delete=True`)
  `action_mail_send` tarafından `env.ref` ile aranır; bulunamazsa `UserError` atılır. Gövde form
  bilgilerini ve portal bağlantısını taşır, `report_template_ids` ile **Service Form PDF'ini ek yapar**;
  `email_from` şirket e-postası yoksa gönderen kullanıcıya düşer.
- Portal taban URL'i `portal.mixin` üzerinden `/my/operation_forms_detail/<id>` olarak `_compute_access_url`
  içinde sabitlenmiştir; denetleyici yolları bu adla eşleşir. İmza uçları sayfa `?source=` ile açılmazsa
  `source="portal"` kullanır (boş segment yüzünden 404 olmaması için).
- Portal imza kısayolları koşullu: `customer_signature_missing()` / `staff_signature_missing()` (`True` = imza **henüz yok**).
  Buton ve modal gövdesi aynı koşula bağlı → imza alındıktan sonra kısayol görünmez ve boş modal açılmaz.
- Portal erişimi **salt-okunur**: `ir.model.access.csv` portal grubuna `perm_read` verir, yazma yoktur.
  İmza yazımı `_portal_sign_customer` / `_portal_sign_staff` üzerinden, alan listesi sabit ve `sudo()` ile
  yapılır; yük base64 doğrulanır (portal imza widget'ı `data:` öneki olmadan sadece base64 gönderir).
- `res_partner._compute_display_name`, `contact_display='name_only'` bağlamında yalnız adı döner; form
  görünümü bu bağlamı `contact_id` alanına geçirir.
- Görseller: `static/description/icon.png`, `icon.svg`, `portal.png`; manifest `images` yalnız `icon.png`
  gösterir. `templates/pdf_header_footer.xml` içindeki `external_forms` şablonu **paylaşılan başlık/altlık
  düzenidir**: bu modülün `service_form_pdf` raporu ve `field_operation_disinfect` raporu onu çağırır;
  alt bilgi IBAN'ı artık şirketin kendi `bank_ids` kayıtlarından gelir (eskiden sabit yazılıydı).
- Etiket notu: `service_type` = "Service Type Code", `user_id` = "Created By User" (kurulumdaki
  "Service Type" / "Created by" etiket çakışması bu şekilde giderildi).
- Bu modül `field_operation_geolocation` (harita + konumlandırma), `field_operation_whatsapp`
  (WhatsApp), `field_operation_pest` ve `field_operation_disinfect` (dezenfeksiyon) modüllerinin
  tabanıdır; hepsi form/liste görünümlerini inherit eder.

## 10. Değişiklik kaydı

**2026-10-12 — inceleme sonrası düzeltmeler, 2. tur ((h) + (i); aynı sürüm, `-u` gerektirir)**

- **"Create Form" butonu:** koşul `status in ('draft','done','cancel') and forms_count == 0` idi; bu, formu olan **her** operasyonda
  butonu görünür bırakıyor ve tıklandığında `UserError: This operation already has a form.` veriyordu →
  `invisible="forms_count != 0 or status in ('draft','done','cancel')"` (yalnız açık ve formsuz operasyonda görünür).
  Sunucu tarafı kontrol zaten vardı, değişen yalnız görünürlük.
- **Portal imza kısayolları:** `customer_signed()` / `staff_signed()` metotları imza **yokken** `True` dönüyordu (adı ters);
  `customer_signature_missing()` / `staff_signature_missing()` olarak yeniden adlandırıldı (mantık aynı, ad artık doğru).
  "Customer Sign" / "Staff Sign" kısayolları bu koşula bağlandı: imza alındıktan sonra buton **hiç görünmüyor** (eskiden
  tıklanınca boş bir modal açılıyordu). `HttpCase` testi iki yönü de doğruluyor: imzadan önce iki kısayol da var,
  müşteri imzasından sonra müşteri kısayolu yok / personel kısayolu duruyor.
- **Testler:** 14 → **15 test**, hepsi yeşil (`soft_gantt_check`); `pre-commit` 11/11 Passed; i18n msgid kümesi değişmedi (161 = 161).

**2026-10-12 — inceleme sonrası düzeltmeler (sürüm 19.0.1.1.0 kalır, `-u` gerektirir; migration yok)**

- **Form numarası:** `create()` alan varsayılanı olan `/` ile karşılaştırmıyordu; istemciden (menüden New) yaratılan form
  artık `FOF-` numarası alır. Ölçüm: `default_get(['name'])` → `/`; eski kodda `create({'name':'/'})` → `/`, `create({})` → `FOF-00011`.
- **`signed` türetilmiş alan oldu:** `customer_signature` ve `staff_signature` doluysa `True` (`_compute_signed`, saklanmaz).
  Canlı ölçüm: 6.323 formda `signed=True` **1**, oysa 6.270 formda `staff_signed_by` dolu → bayrak artık imza görüntülerinden türer.
- **`contact_mobile` / `service_type` → `readonly=True`:** yazma karşı tarafa akıyordu. Ölçüm: forma `contact_mobile` yazmak
  `res.partner.phone`'u değiştirdi (111222333 → 999888777 → 555444333).
- **Ölü alanlar kaldırıldı:** `document_no`, `internal_notes` (canlıda 0/6.275 dolu, v18 kopyasında `# Slinecek`).
  Kolonlar DB'de kalır (Odoo kolon düşürmez).
- **Yeni PDF raporu "Service Form":** `templates/service_form_pdf.xml` (`ir.actions.report`, `binding_type=report`) paylaşılan
  `external_forms` düzenini kullanır; e-posta şablonu `report_template_ids` ile form PDF'ini ek yapar, gövde form bilgileri +
  portal bağlantısı ile dolduruldu, `email_from` şirket e-postası yoksa kullanıcıya düşer.
- **`templates/pdf_header_footer.xml`:** sabit IBAN → şirketin `bank_ids` kayıtları, `t-raw` → `t-out`, `t-else="else"` →
  `t-else=""`, yorumlu bloklar ve bozuk CSS (`object-fit: owerflow`, `#color:`) temizlendi, şablona `name=` verildi;
  manifestteki "hiçbir rapor kullanmıyor" yorumu gerçekle değiştirildi (dezenfeksiyon raporu + bu modülün raporu).
- **i18n:** `.pot` ve `tr.po` koddan yeniden üretildi: 118 → **161 msgid**, koddan gelen 53 yeni string eklendi, 10 ölü kayıt
  düştü, 33 yeni çeviri yazıldı (kalan 14 kayıt kullanıcıya görünmeyen teknik metin). `i18n/tr.mo` silindi — Odoo 19 `.mo`
  okumaz (`tools/translate.py` yalnız `<modül>/i18n/<dil>.po` yükler) ve dosya zaten git'te izlenmiyordu (`*.mo` ignore).
- **Testler:** 10 → **14 test** (13 `TransactionCase` + 1 `HttpCase`); yeni testler form numarası, `signed` türetimi,
  `contact_mobile` okuma yönü ve PDF raporunun modele bağlı olmasını kapsıyor.
- **Doğrulama:** scratch DB `soft_gantt_check` — `-u field_operation_forms` → **14/14 yeşil**, `0 failed, 0 error(s)`;
  pre-commit (11 hook, ruff + ruff-format dahil) **hepsi Passed**; canlı `uzman_v19`'a dokunulmadı.
- **Sürüm notu:** migration yok, bu yüzden manifest sürümü `19.0.1.1.0` bırakıldı (Apps listesinde "Upgrade" istemi çıkmasın);
  düzeltmeleri almak `-u field_operation_forms` ile olur. Canlı üretim (`uzman_v19`) hâlâ `19.0.1.0.0`'da → bu düzeltmeler oraya
  gitmedi.

**2026-10-10 — inceleme sonrası düzeltmeler (sürüm 19.0.1.1.0)**

- **Arama çökmesi:** "Customer" kutusunun `filter_domain`'i `partner_id` diyordu (modelde yok) →
  `customer_id`. Ölçüm: arama `ValueError: Invalid field field.operation.forms.partner_id` veriyordu.
- **Çift bağ tek yöne indirildi:** `forms_id` artık `operation_id`'den türetilir; `action_done` operasyonu
  `operation_id` üzerinden bulur ve bağ yoksa `UserError` atar (eskiden sessizce hiçbir şey yazmıyordu).
- **Saha görünürlüğü:** kural `status in ('new','completed') AND (team_leader_id = user.id OR
  person_ids.user_id = user.id)` oldu → atanmış teknisyen kendi işini görür, kapanan iş listeden çıkar,
  "My Task" filtresi çalışır hale geldi. Ölçüm (canlı): 4.344 formda lider `person_ids` içinde değildi;
  salt "atanmış personel" kuralı bu görünürlüğü silerdi.
- **Portal artık yazamıyor:** `perm_write` kaldırıldı; imza yazımı denetleyiciden `sudo()` + sabit alan
  listesiyle yapılıyor, yük base64 olarak doğrulanıyor. Ölçüm: portal kullanıcısı eskiden `status='done'`,
  `solution` ve `staff_signature` yazabiliyordu.
- **Mükerrer form bitti:** `action_create_forms` ikinci kez çağrılırsa `UserError`; yetki kontrolü
  (forms_user / office grupları) eklendi. Ölçüm (canlı): 24 operasyonda >1 form, 61 form operasyonsuz.
- **Sunucu tarafı yetki:** `action_done`/`action_cancel`/`action_mail_send` → `forms_manager`,
  `action_draft`/`action_completed` → `forms_user`; çağrı yetkisi yoksa `AccessError`.
- **`_signed_on`:** `fields.Date.today()` → `fields.Datetime.now()` (gece yarısına düşen zaman damgası).
- **Standart:** manifest `description` + boş anahtarlar kaldırıldı, sürüm `19.0.1.1.0`; CRLF → LF, eksik
  satır sonları, ruff 25 → 0 ihlal + `ruff format`; yorumlu ölü bloklar (2 view + controller + şablon) ve
  kullanılmayan import'lar silindi; kod içindeki Türkçe hata mesajı İngilizce oldu; menü adı
  "Filed Forms" → "Field Forms"; portal breadcrumb'ı artık kayıt id'si ve token'ı taşıyor (eskiden
  eşleşmeyen bir URL'e gidiyordu).
- **Doğrulama:** scratch DB `soft_gantt_check` — `-u field_operation_forms` → **10/10 test yeşil**;
  migration sapması yapay veriyle test edildi (`forms_id=NULL` → `-u` → en yeni forma bağlandı);
  ruff 0 ihlal, CRLF 0.
