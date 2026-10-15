# Field Operation Invoice

> Saha operasyonlarından tekli ve konsolide (çoklu) fatura oluşturma, operasyon ile
> `account.move` arasında çift yönlü bağ ve faturalama/ödeme takibi.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.0.1`
> Modül: `field_operation_invoice` · 22 takipli dosya (11 py · 4 xml · 1 csv · 2 çeviri) · 3 sihirbaz modeli + 3 model genişletmesi

Bu doküman modül kodundan üretilmiştir (manifest + Python + XML). Kodda kanıtı olmayan
iş bilgisi `<!-- DOLDURULACAK -->` ile işaretlenmiştir.

## 1. Genel Bakış

- **Tekli faturalama:** `field.operation` formundaki **Create Invoice** butonu
  (`action_create_invoice`) `field.operation.to.invoice.wizard` sihirbazını açar; sihirbaz
  `account.move` (`move_type = 'out_invoice'`) oluşturur ve `account_move_id` alanını bağlar.
- **Konsolide faturalama:** Aynı müşteriye ait, tamamlanmış ve faturalanmamış operasyonlar
  listeden seçilip **Create Consolidated Invoice** sunucu aksiyonu ile
  `field.operation.bulk.invoice.wizard` sihirbazına aktarılır; her operasyon bir satır olur.
- **Durum alanları:** `invoicing` (`billed`/`not_billed`) `account_move_id` üzerinden hesaplanır
  ve **saklanır**, `invoice_count` aynı ilişkiden `0/1` üretir; `payment` (`not_paid`/`partial`/
  `paid`) ise elle işaretlenen, `tracking=True` bir selection alanıdır.
- **Çift yönlü gezinme ve satır bağı:** Operasyon formunda **Invoice**, faturada **Service**
  (`action_show_field_operation`) stat butonu karşı kaydı açar; `account.move.line` üzerine
  `field_operation_id` (indexli m2o) eklenir, satırın kaynağı böylece izlenebilir.
- Kapsam dışı: `account.payment` oluşturma, `payment` alanının otomatik güncellenmesi,
  kısmi fatura/mahsup ve iade (credit note) akışı, vergi varsayılanı **yoktur**.

<!-- DOLDURULACAK: Saha hizmeti faturalarında KDV/tevkifat varsayılanı nasıl belirleniyor (ürün bazlı mı, muhasebe politikası mı)? -->

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `field_operation` | `field.operation` modeli, `view_field_operation_form` / `_list` / `_filter`, `service_group_all` grubu, `status` ve `service_price` alanları |
| `account` | `account.move`, `account.move.line`, `account.view_move_form`, out_invoice tipi ve fatura tarihleri |

## 3. Ana Modeller

| Model | Tür | Eklenenler |
|---|---|---|
| `field.operation` | `_inherit` | `account_move_id` (m2o, tracking), `invoice_count` (compute), `invoicing` (compute, store, readonly=False, tracking), `payment` (selection, tracking), `action_create_invoice()`, `action_view_invoice()` |
| `account.move` | `_inherit` | `field_operation_ids` (one2many ← `account_move_id`), `field_operation_invoice_count` (compute, store), `action_cancel()` / `unlink()` override'ları, `action_show_field_operation()` |
| `account.move.line` | `_inherit` | `field_operation_id` (m2o, `index=True`) |
| `field.operation.to.invoice.wizard` | `_name` (TransientModel) | Tekli fatura sihirbazı |
| `field.operation.bulk.invoice.wizard` | `_name` (TransientModel) | Konsolide fatura sihirbazı |
| `field.operation.bulk.invoice.wizard.line` | `_name` (TransientModel) | Satır: `operation_id`, `product_id`, `description`, `price_unit` |

## 4. Roller ve Güvenlik

- `security/ir.model.access.csv` üç sihirbaz modeli için tam yetkiyi yalnızca
  **`field_operation.service_group_user`** grubuna verir (worker grubu kullanamaz).
- Formdaki **Create Invoice** ve **Invoice** butonları
  `groups="field_operation.service_group_all"` ile sınırlanır (ACL ile tutarlıdır).
- **Create Consolidated Invoice** sunucu aksiyonu
  `group_ids = [(4, ref('field_operation.service_group_all'))]`, yalnızca liste görünümünde.
- **Kayıt kuralı (ir.rule) eklenmez**; görünürlük çekirdek `field_operation` ve `account`
  kayıt kurallarına bırakılır. Fatura oluşturma `sudo` kullanmaz; yetki yoksa `AccessError`.

## 5. Ana Akış

**Tekli fatura**

| Adım | Kayıt / Metod | Detay |
|---|---|---|
| Buton | `field.operation.action_create_invoice` | Yalnızca `status = 'done'` iken görünür |
| Sihirbaz | `field.operation.to.invoice.wizard.default_get` | `default_field_operation_id` veya `active_id`; `partner_id`, `company_id`, `service_price`, `description` operasyondan doldurulur |
| Ürün seçilirse | `_onchange_product_id` | Açıklama boşsa ürün adı, fiyat `0` ise ürün `list_price` değeri yazılır |
| Doğrulama | `action_create_invoice` | Zaten fatura varsa, fiyat ≤ 0 ise veya müşteri boşsa `UserError` |
| Kayıt | `account.move.create` | `move_type='out_invoice'`, tek satır (`quantity=1`), `field_operation_id` satıra yazılır |
| Bağlama | `field.operation.write` | `account_move_id = invoice.id` |

**Konsolide fatura:** Sunucu aksiyonu sihirbazı `active_ids` ile açar (`target='new'`).
`default_get` üç kapı uygular: farklı müşteri, `status != 'done'` veya `account_move_id` dolu
operasyon → `UserError`. `action_create_invoice` satırları `account.move`'a çevirir
(`quantity=1`, `product_uom_id` yalnızca ürün seçiliyse) ve faturayı açar.

**İptal/silme:** `account.move.action_cancel()` ve `unlink()` override'ları, `super()` sonrası
ilişkili operasyonların `account_move_id` alanını boşaltır — operasyon "faturalanmamış"a döner.

## 6. Alan Eşlemeleri / Liste Kolonları

`field.operation` liste görünümüne eklenen kolonlar (mevcut `name` alanından sonra,
`priority=7` birleştirme):

| Kolon | Görünüm | Renk kuralı |
|---|---|---|
| `account_move_id` | `column_invisible="1"` | Yalnızca veri amaçlı |
| `invoicing` | badge, `optional="show"` | `not_billed` → info, `billed` → danger |
| `payment` | badge, `optional="show"` | `not_paid` → info, `partial` → danger, `paid` → success |

Form görünümü: `create_date` sonrası `invoicing` (grup: `service_group_all`), `payment`,
`account_move_id` (gizli); `button_box`'ta **Invoice** stat butonu (`invoice_count == 0` iken
gizli); header'da **Create Invoice** (`status not in ('done',)` iken gizli). Fatura formunda
`button_box`'a **Service** stat butonu (`field_operation_invoice_count`, `fa-tasks`) eklenir.
Sihirbaz alanları: `invoice_date` (zorunlu), `invoice_date_due`, `company_id`, `currency_id`; satırda `product_id` (domain `type='service'`), `description`, `price_unit`.

## 7. Arama Filtreleri

- Modül klasik arama filtresi/facet tanımlamaz; operasyon arama görünümüne **search panel**
  alanları ekler (`//searchpanel` → `invoicing`, `payment`; `enable_counters=1`, `fa-users`).
- Konsolide sihirbaza erişim **sunucu aksiyonu bağlaması** iledir (`binding_view_types = list`);
  seçimden sonra **Action** menüsünden çalıştırılır, sihirbaz listesinde ek filtre yoktur.

## 8. Test Kapsamı

`tests/test_field_operation_invoice.py` — 8 test, hepsi yeşil (`--test-tags /field_operation_invoice`):

1. Tekli sihirbaz: `default_get` + fatura oluşturma, satır/servis bağı, sayaçlar (`invoicing`, `invoice_count`).
2. Tekli sihirbaz guard'ları: fiyat ≤ 0 ve mükerrer fatura.
3. İptal edilen faturaya servisin **bağlı kalması** (bilinçli davranış, regresyon testi).
4. Faturanın silinmesinde bağın boşalması ve `invoicing`ın tazelenmesi.
5. Konsolide sihirbaz: iki servis → tek fatura, iki satır, doğru toplam, iki yönlü bağ.
6. Konsolide guard'ları: farklı müşteri, bitmemiş servis, faturalanmış servis, müşterisiz sihirbaz.
7. Bayat konsolide sihirbazın ikinci fatura üretememesi (submit anında yeniden kontrol).
8. `payment` alanının elle tutulduğunun, faturadan türetilmediğinin doğrulanması.

## 9. Geliştirici Notları

- Migration yok (`migrations/` bulunmuyor); çeviri dosyaları
  `i18n/field_operation_invoice.pot` ve `i18n/tr.po` (50 `msgid`), `tr.mo` yoktur.
- Görsel: `static/description/` altında `icon.png`, `icon.svg`, `index.html`; manifest `images` alanı `icon.png`'i
  gösterir. Kaynak dosyalar LF satır sonu kullanır.
- Faturalama akışı tamamen sihirbaz tabanlıdır; `sale.order`/`stock` entegrasyonu yoktur,
  bu yüzden gelir hesabı `account.move` varsayılanlarına bağlıdır.
- `__pycache__/` ve `.pyc` dosyaları diskte var, `.gitignore` kapsamındadır.

## 10. Değişiklik kaydı

**2026-10-10 — inceleme sonrası düzeltmeler (sürüm 19.0.1.0.1)**

- **Ölü `action_cancel` override'ı kaldırıldı:** Odoo'da `account.move.action_cancel` yok; metot hiç
  çağrılmıyordu ve vaat ettiği "iptalde bağı kopar" davranışı gerçekleşmiyordu. İptal edilen faturaya
  servisin bağlı kalması artık bilinçli davranış (test 3).
- **Silmede bağ ORM üzerinden boşaltılıyor:** m2o cascade'i kolonu doğrudan SQL'de boşalttığı için
  servisin saklanan `invoicing` alanı "Billed" olarak bayat kalıyordu; artık `unlink` öncesinde ORM
  ile yazılıyor (test 4).
- **Konsolide sihirbaz submit anında yeniden doğruluyor:** bayat sihirbaz aynı servis için ikinci fatura
  üretip bağı sessizce taşıyabiliyordu; kontrol hem `default_get` hem `action_create_invoice` içinde
  (test 7) ve bağ artık satırlardan (`line_ids.operation_id`) türetiliyor.
- **Alan dokümantasyonu:** `invoicing` (elle girilen değerin hesap tarafından ezilebileceği) ve `payment`
  (faturayla senkronize **edilmeyen**, elle tutulan alan) `help` metinleriyle belgelendi (test 8).
- **Standart:** manifestteki `description` ve boş `demo`/`assets`/`external_dependencies` kaldırıldı,
  sürüm `19.0.1.0.1`; CRLF → LF, eksik satır sonları, ruff (22 → 0 ihlal) + `ruff format`; iki view'daki
  yorumlanmış ölü bloklar ve kullanılmayan `operations_by_move` sözlüğü silindi; yorumlar İngilizce.
