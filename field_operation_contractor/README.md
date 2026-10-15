# Field Operation Contractor

> Taşeron (ana yüklenici / alt yüklenici) iş kayıtları — taşeron partneri, sorumlu kullanıcı
> ve o taşerona bağlı müşterilerin takibi.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.0.0`
> Modül: `apps/saha/field_operation_contractor` · 15 dosya · 1 yeni model + 2 inherit (field.operation, res.partner)

Bu doküman modül kodundan üretilmiştir (manifest + models + security + views).
Kodda kanıtı olmayan iş bilgisi `<!-- DOLDURULACAK -->` ile işaretlenmiştir.

## 1. Genel Bakış

Saha işlerini taşeron firmalara devretme sürecinin ana verisini ve bağlantılarını kurar.

- **Taşeron iş kaydı:** `field.operation.contractor` — iş adı, taşeron partneri (zorunlu),
  sorumlu kullanıcı (zorunlu), tip (`main` = ana yüklenici / `sub` = alt yüklenici), açıklama.
- **Müşteri bağlantısı:** `res.partner.service_contractor_id` alanı ile bir müşteri bir taşerona
  bağlanır; taşeron formundaki **Customers** sekmesi ve `customer_count` akıllı butonu bu listeyi gösterir.
- **Bayrak senkronizasyonu:** taşeron kaydı oluşturulduğunda/güncellendiğinde ilgili partnerin
  `is_contractor` alanı `True` yapılır; son taşeron kaydı silindiğinde veya partner değiştirildiğinde
  `False`'a çekilir (`create` / `write` / `unlink`).
- **İş tarafı:** `field.operation.contractor_id` alanı iş formuna eklenir; müşterinin bağlı olduğu
  taşeron `_onchange_partner_id` ile otomatik önerilir.
- **Partner formu:** `is_contractor` ve `service_contractor_id` alanları birbirini dışlayan
  `invisible` koşullarıyla gösterilir (bir partner ya taşeron ya müşteri tarafında görünür).

Kapsam dışı: taşeron hakedişi/faturası, sözleşme metni, puantaj ve onay akışı; taşeron işi ile
`field.operation` arasında zaman/ücret kopyalama yapılmaz (yalnız m2o bağlantı).

<!-- DOLDURULACAK: Bir taşeron işi saha işine (field.operation) nasıl eşlenmeli — 1:1 mi, bir taşeron kaydı çok iş mi? -->

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `field_operation` | `field.operation` modeli ve form view'i (`view_field_operation_form`), `field_operation.service_group_*` grupları, `menu_field_operation_root` menüsü |

## 3. Ana Modeller

| Model | `_description` | Dosya |
|---|---|---|
| `field.operation.contractor` | Field Operation Contractor | `models/field_operation_contractor.py` |
| `field.operation` (inherit) | — | `models/field_operation.py` (`contractor_id`, `ondelete='restrict'`, `tracking=True`) |
| `res.partner` (inherit) | — | `models/res_partner.py` (`service_contractor_id`, `service_contractor_count`, `is_contractor`) |

`field.operation.contractor` alanları: `name` (Job, zorunlu), `active`, `contractor_type`
(main/sub), `partner_id` (zorunlu), `user_id` (zorunlu), `description`, `customer_ids`
(`res.partner.service_contractor_id` üzerinden One2many), `customer_count` (hesaplı).
Modül `mail.thread` içermez — chatter ve takip kaydı yok.

## 4. Roller ve Güvenlik

ACL (`security/ir.model.access.csv`, tek satır):

| Model | Grup | `perm_read,write,create,unlink` |
|---|---|---|
| `field.operation.contractor` | `field_operation.service_group_user` | 1,1,1,1 |

- Yeni grup tanımlanmaz; `field_operation` grupları kullanılır (Office User, Head Office ve
  Admin bu izni `implied_ids` zinciriyle alır).
- **Record rule yok** (`security/` dizininde yalnız ACL dosyası var).
- **Field Worker grubunun bu modele hiç izni yok**; ancak **Contractors** menüsü grup kısıtı
  olmadan `field_operation.menu_field_operation_root` altına eklendiği için (kök menü
  `service_group_worker`'a açık) saha çalışanı menüyü görür — ancak ACL yalnız `service_group_user`'a verildiği için tıklayınca `AccessError` alır.

## 5. Ana Akış

Menü yolu: **Field Operation → Contractors** (sequence 15, `field_operation.menu_field_operation_root` altında).

| Kayıt | Tip | Detay |
|---|---|---|
| `view_field_operation_contractor_form` | `ir.ui.view` | `form string="Contractor Job"`; button_box'ta `action_view_customers` stat butonu (`invisible="customer_count == 0"`); sekmeler: Customers (`customer_ids`: name/phone/email), Description |
| `view_field_operation_contractor_list` | `ir.ui.view` | `list string="Contractor Jobs"`: `name`, `contractor_type` (badge), `partner_id`, `user_id` (avatar), `customer_count` |
| `view_field_operation_contractor_search` | `ir.ui.view` | alanlar: `name`, `partner_id`; filtreler: Subcontractor, Main Contractor; gruplar: Contractor, Type |
| `action_field_operation_contractor` | `ir.actions.act_window` | `res_model=field.operation.contractor`, `view_mode=list,form`, boş liste metni "Create a new Contractor Job" |
| `contractor_field_operation_form_view` | `ir.ui.view` (inherit) | `field_operation.view_field_operation_form`; `service_type_id` alanından **sonra** `contractor_id` |
| `view_field_operation_contractor_partner_form` | `ir.ui.view` (inherit) | `base.view_partner_form`; `lang` alanından sonra `is_contractor` ve `service_contractor_id` |

Butonlar/metotlar: `action_view_customers` → `res.partner` listesi
(`domain=[('service_contractor_id','=',id)]`); partner tarafında `show_service_contractor()`
`field.operation.contractor` listesine yönlendirir.

Otomatik alan akışı: `field.operation` formunda `partner_id` seçildiğinde
`_onchange_partner_id`, partnerin `service_contractor_id` değerini `contractor_id`'ye yazar.

## 6. Alan Eşlemeleri / Liste Kolonları

| Liste | Kolonlar |
|---|---|
| Contractor Jobs | `name`, `contractor_type` (badge), `partner_id`, `user_id` (many2one_avatar_user), `customer_count` |
| Form sekmeleri | Customers: `name`, `phone`, `email` (editable değil); Description: `description` |
| Partner formu (inherit) | `is_contractor` (`invisible="service_contractor_id == True"`), `service_contractor_id` (`invisible="is_contractor == True"`) |
| field.operation formu (inherit) | `contractor_id` (yalnız form; `optional="hide"` ile) |

`name` alanı görünen ad olarak kullanılmaz: `_compute_display_name` partner adını döndürür,
yani kaydın ekrandaki etiketi taşeron firma adıdır (iş adı değil).

## 7. Arama Filtreleri

| Model | Filtreler |
|---|---|
| `field.operation.contractor` | Subcontractor (`contractor_type='sub'`), Main Contractor (`contractor_type='main'`); gruplama: Contractor (`partner_id`), Type (`contractor_type`) |
| `field.operation` | Bu modül `contractor_id` için **arama alanı/filtresi eklemez** — iş listesinde taşeron bazlı filtre yoktur |
| `res.partner` | Ek filtre yok (yalnız `field_operation` modülünün "Services" filtresi geçerli) |

## 8. Test Kapsamı

Test yok: `tests/` dizini bulunmuyor. Öneri: (1) taşeron kaydı oluşturulunca partnerin
`is_contractor` bayrağının `True`, son kayıt silinince `False` olması, (2) birden fazla taşeron
kaydı aynı partneri kullandığında bayrağın erken `False`'a düşmemesi, (3) Field Worker
kullanıcısının `field.operation.contractor` üzerinde `AccessError` alması ve menünün
görünmemesi — `TransactionCase`, `@tagged('post_install','-at_install')`.

## 9. Geliştirici Notları

- **Migration yok:** `migrations/` dizini bulunmuyor.
- **Sequence/cron yok:** modülde yalnız ACL + 3 view dosyası yüklenir; veri dosyası yoktur.
- **View isimleri:** `res.partner.field.operation.contractor`, `field.operation.contractor`
  adları diğer modüllerin view adlarıyla kolayca karışabilir (kayıt id'leri farklı olduğu için
  teknik çakışma yoktur).
- **`contractor_id` kısıtı:** `ondelete='restrict'` — taşeron kaydı, üzerinde iş varsa silinemez;
  pasifleştirme (`active=False`) desteklenir.
- **i18n:** `i18n/field_operation_contractor.pot` + `i18n/tr.po` (29 `msgid` girdisi).
- **Statik:** `static/description/` altında `icon.png`, `icon.svg`, `portal.png`, `index.html`
  (portal şablonu bu modülde yok, `portal.png` görsel arşiv amaçlı duruyor).
