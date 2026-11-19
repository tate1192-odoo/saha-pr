# Field Operation Contract Management

> Saha (Field Operation) servisi için **recurring (yinelenen) sözleşme yönetimi**.
> Sales ↔ Invoicing ↔ Field Service arasında köprü kurar. Softteknik Bilişim,
> Odoo 19, AGPL-3, sürüm `19.0.1.3.0`.

Modül; tek seferlik satış yerine **periyodik servis** veren işler için tasarlanmıştır
(aylık bakım, haftalık denetim, yıllık sözleşmeler vb.). Müşteriye bir sözleşme
açılır, her periyotta otomatik olarak bir **Satış emri (sale.order)** ve bir
**Saha operasyonu (field.operation)** üretilir; üretilen adetler sözleşme
satırında takip edilir.

---

## İçindekiler

1. [Genel Bakış](#1-genel-bakış)
2. [Roller ve Güvenlik](#2-roller-ve-güvenlik)
3. [Kontrat Oluşturma — 2 Senaryo](#3-kontrat-oluşturma--2-senaryo)
4. [Kontrat Yaşam Döngüsü](#4-kontrat-yaşam-döngüsü)
5. [Recurring (Yinelenen) Servis Takibi](#5-recurring-yinelenen-servis-takibi)
6. [Satış ↔ Sözleşme ↔ Field Operation Zinciri](#6-satış--sözleşme--field-operation-zinciri)
7. [PDF Raporu](#7-pdf-raporu)
8. [Bilinen Sınırlamalar / Teknik Borç](#8-bilinen-sınırlamalar--teknik-borç)
9. [Test Kapsamı](#9-test-kapsamı)
10. [Geliştirici Notları](#10-geliştirici-notları)

---

## 1. Genel Bakış

### Ne çözer?

Saha servisi veren şirketlerde tipik ihtiyaç:

> "X müşterisi için 12 aylık bakım sözleşmesi açayım; sistem her ay otomatik
> bir faturalık satış oluştursun ve saha ekibine bir operasyon düşsün;
> 12. aydan sonra sözleşme tükenmeli."

Bu modül tam olarak bunu yapar. **Tek sözleşme → çok satış + çok operasyon**
üretim modeli.

### Bağımlılıklar (`__manifest__.py` → `depends`)

| Modül | Sağladığı |
|---|---|
| `field_operation` | `field.operation` modeli, `field.operation.type` (servis tipi), gruplar (`service_group_user`, `service_group_manager`) |
| `field_operation_sale` | `sale.order.order_types` alanı (`service`/`stock`); bu modül `contract`/`invoice` seçeneklerini ekler (`models/sale_order.py` → `order_types`) |
| `portal` | Müşteri portalı altyapısı |

### Ana modeller

| Model | Dosya | Rolü |
|---|---|---|
| `field.operation.contract` | `models/field_operation_contract.py` | Sözleşme header (müşteri, tarih, durum, recurring ayarı) |
| `field.operation.contract.line` | `models/field_operation_contract_line.py` | Sözleşme satırı (ürün, adet, periyot, kalan servis) |
| `field.operation.contract.tag` | `models/field_operation_contract_tag.py` | Etiket |
| `sale.order.contract.wizard` | `wizard/sale_order_to_contract_wizard.py` | Satıştan sözleşme dönüşüm sihirbazı |
| `service.contract.recurring.mixin` | `models/service_contract_recurring_mixin.py` | Recurring hesaplama abstract modeli (OCA Contract'tan ilham) |

### Önemli alan eşlemeleri (terminoloji)

| Saha modülü | Anlamı |
|---|---|
| `total_service` | Sözleşmede söz verilen **toplam servis adedi** (örn. 12 = yıllık 12 ziyaret) |
| `generated_occurrences` | Şu ana kadar **üretilmiş** adet |
| `remaining_count` | `max(0, total_service - generated_occurrences)` — kalan adet (`models/field_operation_contract_line.py` → `_compute_remaining_count`) |
| `line_recurrence` | True → her satır kendi periyodunda; False → header periyodu geçerli |

---

## 2. Roller ve Güvenlik

### Grup hiyerarşisi (`field_operation/security/res_groups.xml`)

```
service_group_worker   (Field Worker)
        ↓ implied
service_group_user     (Office User)     ← contract modülü ana grubu
        ↓ implied
service_group_all      (Head Office)
        ↓ implied
service_group_manager  (Admin)
```

### ACL (`security/ir.model.access.csv`)

**Tek grup**, tüm modeller için tam CRUD: `field_operation.service_group_user`.

| Model | Grup | R | W | C | D |
|---|---|---|---|---|---|
| `field.operation.contract` | `service_group_user` | 1 | 1 | 1 | 1 |
| `field.operation.contract.line` | `service_group_user` | 1 | 1 | 1 | 1 |
| `field.operation.contract.tag` | `service_group_user` | 1 | 1 | 1 | 1 |
| `sale.order.contract.wizard` | `service_group_user` | 1 | 1 | 1 | 1 |
| `sale.order.contract.wizard.line` | `service_group_user` | 1 | 1 | 1 | 1 |

Manager'a özel tek şey: formdaki **"Run Cycle (Test)"** butonu
(`views/field_operation_contract_view.xml` → `action_recurring_process`).

### Multi-company ve portal izolasyonu

`security/security.xml` üç `ir.rule` taşır:

- `rule_field_operation_contract_company` — `company_id in company_ids`
- `rule_field_operation_contract_line_company` — `contract_id.company_id in company_ids`
- `rule_field_operation_contract_portal` — portal kullanıcısı yalnızca
  `user.partner_id.commercial_partner_id` zincirindeki sözleşmeleri görür
  (`base.group_portal`)

Yani şirket izolasyonu ve portal kısıtı vardır; `company_id` alanı
`base.group_multi_company` ile görünür.

---

## 3. Kontrat Oluşturma — 2 Senaryo

Sözleşme 2 farklı yoldan oluşturulabilir:

| Senaryo | Tetikleyici | Araç | Kaynak kod |
|---|---|---|---|
| **A. Manuel** | Saha menüsü → Contracts → New | Direkt form | `views/field_operation_contract_view.xml` → `action_field_operation_contract` |
| **B. Satıştan** | `sale.order` `order_types='contract'` → **Create Contract** butonu | Wizard | `wizard/sale_order_to_contract_wizard.py` |

### Senaryo A — Manuel Olarak Sözleşme Açmak

En yaygın yol. Ofis kullanıcısı doğrudan sözleşme oluşturur.

**Adımlar:**

1. **Saha → Contracts → New** (`action_field_operation_contract`,
   `views/field_operation_contract_view.xml`).
2. **Zorunlu alanları doldur:**
   - `partner_id` — müşteri (required, `models/field_operation_contract.py` → `partner_id`)
   - `date_start` — başlangıç (required, default bugün)
   - `service_type_ids` — servis tipleri (required M2M)
3. **Recurring modu seç** (sol grup):
   - `line_recurrence = False` (varsayılan) → **header bazlı**: tüm satırlar ortak
     periyotla çalışır. Sağdaki `recurring_rule_type`, `recurring_interval`,
     `recurring_generation_type`, `recurring_next_date` alanları görünür.
   - `line_recurrence = True` → **satır bazlı**: her satırın kendi periyodu.
     Sağdaki header recurring alanları gizlenir (`views/field_operation_contract_view.xml`
     → `group name="right"`); satır bazlı alanlar `contract_line_ids` listesinde açılır.
4. **Satırları ekle** ("Services & Products" sekmesi):
   - `product_id` (yalnızca `type='service'`, `models/field_operation_contract_line.py` → `product_id`)
   - `total_service` — söz verilen toplam servis adedi (örn. 12)
   - `price_unit`, `discount`
   - Satır bazlı modda: `recurring_rule_type`, `recurring_interval`,
     `recurring_next_date` her satır için ayrı girilir
5. **Confirm** butonuna bas → `state='confirmed'`. Header modda boşsa
   `recurring_next_date = date_start` set edilir (`models/field_operation_contract.py`
   → `action_confirm`). Onaydan sonra header alanları ve satırlar kilitlenir
   (`readonly="state != 'draft'"`).
6. Artık sözleşme cron tarafından işlenmeye hazır.

**Sözleşme no** otomatik üretilir: `FOC/00001`, `FOC/00002`, ...
(`data/ir_sequence_data.xml`, `models/field_operation_contract.py` → `create`).

> **Not — `name` fallback davranışı:** Satır `name` boşsa, `contract_line.create()`
> override'ı ürünün açıklamasını yazar (`models/field_operation_contract_line.py` →
> `create`, `get_product_multiline_description_sale()`). Ürün de yoksa `"Service Line"`.
> Ürünün `service_type_id`'si de satıra kopyalanır; boşsa sözleşmenin ilk servis tipi yazılır.

### Senaryo B — Satış Siparişinden Sözleşme Oluşturmak

Bir satış siparişini recurring sözleşmeye dönüştürür. Tipik kullanım: müşteri
 ilk yıl için teklif alınca, teklif onaylanınca sözleşmeye çevrilir.

**Adımlar:**

1. **Satış siparişi aç**, `order_types = 'contract'` seç.
   - `order_types` alanı `field_operation_sale` modülünde tanımlı
     (`field_operation_sale/models/sale_order.py`); bu modül `'contract'` ve
     `'invoice'` seçeneklerini ekler (`models/sale_order.py` → `order_types`).
2. **Create Contract** butonu header'da görünür — sadece `order_types='contract'`
   VE `service_contract_id` boşsa (`views/sale_order_view.xml`).
3. **Wizard açılır** (`sale.order.contract.wizard`). `default_get` otomatik:
   - Sale order'dan `partner_id`, `company_id`; `date_start` = bugün,
     `date_end` = bugün + 1 yıl.
   - Sadece **service product** satırları wizard'a kopyalanır; `consu`/`product`
     tipler atlanır.
   - `service_type_ids` ürünlerin `service_type_id` alanından toplanır.
   - Her satıra varsayılan: `recurring_interval=1`, `recurring_rule_type='monthly'`,
     `recurring_next_date` = sözleşme başlangıcı (boşsa bugün); adet, fiyat, iskonto
     ve vergiler sale order satırından kopyalanır.
   - Servis lokasyonu varsayılanı: `partner_shipping_id` → `address_get('delivery')`
     → müşteri adresi.
4. Kullanıcı satırlarda **lokasyon**, **periyot**, **adet** düzeltebilir.
5. **Create Contract** → `action_create_contract` (`wizard/sale_order_to_contract_wizard.py`):
   - **Satır doğrulaması** (`_validate_lines`): ürün service mi, miktar > 0 mı,
     lokasyon ve ilk servis tarihi dolu mu, satır tarihi sözleşme aralığında mı.
     Her ihlal `UserError` ile döner.
   - **Otomatik mod kararı** (`action_create_contract`): Eğer satırların `recurring_rule_type`,
     `recurring_interval` veya `recurring_next_date` değerlerinden herhangi biri
     farklıysa `line_recurrence=True` set edilir. Kullanıcıya uyarı gösterilir.
   - Sözleşme oluşturulur; kaynak **sale.order** `service_contract_id` ile
     sözleşmeye bağlanır ve kapatılır (`cancel`). Kaynak teklifin tekrar
     confirm/fatura edilmesini engelleyen sunucu guard'ı vardır.
   - Dönüş değeri: sözleşme formunu açan `ir.actions.act_window`.

**Satır eşlemesi (wizard → sözleşme satırı)**, `wizard/sale_order_to_contract_wizard.py` → `action_create_contract`:

| Wizard satırı | Sözleşme satırı | Not |
|---|---|---|
| `product_uom_qty` | `total_service` | **Miktar → servis adedi** (anlamsal dönüşüm) |
| `price_unit` | `price_unit` | |
| `discount` | `discount` | |
| `uom_id` | `uom_id` | |
| `service_type_id` | `service_type_id` | |
| `location_id` | `location_id` | |
| `recurring_*` | `recurring_*` | |
| `recurring_next_date` | `date_start` | Line.next_date > wizard.date_start önceliği |
| `date_end` | `date_end` | Line.date_end > wizard.date_end önceliği |

> **Vergi eşlemesi var.** Wizard satırı `tax_id` alanını taşır ve
> `action_create_contract` vergileri sözleşme satırına kopyalar
> (`tests/test_sale_order_contract_wizard.py` → `test_action_create_contract_maps_taxes`).
> Sözleşme satırındaki vergi üretilen sale.order satırına taşınmaz; o satır ürünün
> varsayılan vergileriyle oluşur (bkz. [Bölüm 8](#8-bilinen-sınırlamalar--teknik-borç)).

> **Sözleşme şartları (Contract Terms):** Formdaki **Contract Terms** sekmesinden
> `contract_terms` Html alanına manuel girilir. PDF ve portalda gösterilir.

---

## 4. Kontrat Yaşam Döngüsü

### State machine

```
                    action_confirm
        ┌────────────────────────────────┐
        ▼                                │
   ┌─────────┐                      ┌─────────┐
   │  draft  │──── action_confirm ──▶│confirmed│
   └─────────┘                      └─────────┘
        ▲                                │
        │ action_set_to_draft            │ action_cancel
        │                                ▼
        │                            ┌─────────┐
        └─── action_set_to_draft ────│ expired │
                                     └─────────┘
                                          ▲
                                          │ action_expire (manuel)
                                          │
                                     ┌─────────┐
                                     │ expired │  ← date_end geçse bile OTOMATİK geçmez
                                     └─────────┘

   ┌─────────┐
   │  cancel │ ◀── action_cancel (confirmed'dan)
   └─────────┘
```

> State seçimi dört değer taşır: `draft`, `confirmed`, `expired`, `cancel`.
> Eski `to_renew` state'i kaldırıldı (`tests/test_contract_review_fixes.py` →
> `test_to_renew_state_removed`); `action_renew` implement edilmemiş.

### State geçiş metodları

| Metot | Dosya:Line | Koşul / Yan etki |
|---|---|---|
| `action_confirm` | `models/field_operation_contract.py` → `action_confirm` | Sadece `draft` onaylanır; satır yoksa `UserError`. Header modda `recurring_next_date` boşsa `date_start` set edilir. |
| `action_cancel` | → `action_cancel` | Bağlı `draft`/`sent` sale.order'ları ve `draft` operasyonları da iptal eder, sonra `state='cancel'`. |
| `action_set_to_draft` | → `action_set_to_draft` | Koşulsuz `state='draft'`. |
| `action_expire` | → `action_expire` | Koşulsuz `state='expired'`. **Sadece manuel buton.** |
| `action_renew` | — | **Yok** (planlanmamış). |

İmza alanları (`signature_status`, `signatory_name`, `signature_date`)
`action_confirm`'de değil, portal kabul route'unda
(`controllers/controllers.py` → `portal_contract_accept`) set edilir.

### ⚠ Otomatik expire YOK

`date_end` geçse bile sözleşme `confirmed` kalır. Cron
(`data/ir_cron_data.xml:4-14`) sadece `action_recurring_process`'i çağırır,
`expired`'e düşürmez. Domain filtresi (`_get_contracts_to_process_domain`)
`date_end >= today` şartı arar ama **uygunsuz sözleşmeleri
expire etmez**, sadece recurring işlemesini atlar.

Manuel `action_expire` butonu formda görünür (statusbar'da `expired` gösteriliyor).

### Alan kilidi

Form view'de header alanları ve `contract_line_ids` listesi
`readonly="state != 'draft'"` ile kilitlidir: `draft` dışındaki her durumda
(confirmed, expired, cancel) alanlar ve satırlar düzenlenemez. Hesaplanan
`recurring_next_date`, `last_date_processed`, `generated_occurrences` ve
`remaining_count` her durumda salt okunurdur.

---

## 5. Recurring (Yinelenen) Servis Takibi

Modülün kalbi burası. İki moddan biri seçilir; her mod farklı üretim mantığı
çalıştırır.

### 5.1 İki mod karşılaştırması

| Özellik | Header-based (`line_recurrence=False`) | Line-based (`line_recurrence=True`) |
|---|---|---|
| **Tetikleme** | Sözleşmenin `recurring_next_date`'i | Her satırın kendi `recurring_next_date`'i |
| **Hazırlama metodu** | `_prepare_header_recurrence_values` | `_prepare_line_recurrence_values` |
| **Üretilen sale.order `order_types`** | `'invoice'` | `'service'` |
| **Field operation `start_date`** | işlenen dönemin servis tarihi (`due_date` = `recurring_next_date`) | `line.recurring_next_date` |
| **`date_order`** | aynı servis tarihi | lokasyondaki en erken servis tarihi |
| **Tarihi kim ilerletir** | Sözleşme header'ı | Her satır ayrı ayrı |
| **Kullanım** | Tek tip servis, tek periyot | Çok lokasyon/farklı periyotlar |

### 5.2 Üretim akışı (cron → records)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Cron (her 6 saat)        data/ir_cron_data.xml                      │
│  ↓                                                                   │
│  action_recurring_process()   models/field_operation_contract.py     │
│  ↓                                                                   │
│  _get_contracts_to_process_domain(): state=confirmed, active=True,   │
│          date_end IS NULL OR date_end >= today                       │
│  ↓                                                                   │
│  Şirketlere göre grupla, with_company context'i                      │
│  ↓                                                                   │
│  _recurring_create_sale_ops()                                        │
│  │  3 fazlı bulk pattern:                                            │
│  │                                                                   │
│  │  Faz 1 — Hazırlık (DB yazma yok)  _prepare_recurrence_values      │
│  │  ├─ Her contract için mod seçimi:                                 │
│  │  │   line_recurrence? → _prepare_line_recurrence_values           │
│  │  │   else            → _prepare_header_recurrence_values          │
│  │  ├─ Lokasyon bazlı gruplama (_group_lines_by_location)            │
│  │  └─ unique_key ile SO ↔ FieldOp eşleştirme                        │
│  │                                                                   │
│  │  Faz 2 — Toplu oluşturma                                          │
│  │  ├─ Tüm sale.order'lar BULK create                                │
│  │  ├─ key_to_so_id mapping                                          │
│  │  └─ field.operation'lar create + sale_id                          │
│  │                                                                   │
│  │  Faz 3 — Takip güncellemeleri                                     │
│  │  ├─ generated_occurrences += 1                                    │
│  │  ├─ last_date_processed / recurring_next_date ilerlet             │
│  │  └─ message_post ile log                                          │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.3 Üretilen kayıt sayısı (örnek)

Bir sözleşmede **3 servis satırı**, **2 farklı lokasyon** varsa ve bugün
processing tarihine geldiyse:

- **Header mod**: 2 sale.order (lokasyon başına 1) + 3 field.operation
  (satır başına 1; hepsi işlenen dönemin servis tarihinde)
- **Line mod**: 2 sale.order + 3 field.operation (ama her field.operation
  kendi satırının `recurring_next_date`'inde — farklı günlerde olabilir)

### 5.4 Servis adedinin tükenmesi

```
total_service         = 12      (sözleşmede söz verilen)
generated_occurrences = 0  → 1 → 2 → ... → 12     (her periyotta artar)
remaining_count       = 12 → 11 → 10 → ... → 0    (compute, _compute_remaining_count)
```

`remaining_count = 0` olduğunda:

- Satır recurring domain'inde filtrelenir (`_prepare_header_recurrence_values`,
  `_prepare_line_recurrence_values`).
- Artık o satır için SO/FieldOp üretilmez.
- **Sözleşme `confirmed` kalır** — otomatik expire yok. Manuel `action_expire`
  gereklidir.

### 5.5 Tarih hesaplama (mixin)

`models/service_contract_recurring_mixin.py` OCA Contract'tan ilhamla:

- `_get_default_recurring_offset`: `beginning`/`monthlylastday` → 0, `end` → 1.
- `get_relative_delta`: `relativedelta` factory. `monthlylastday` dönemi ayın
  **ilk gününe** çıpalar (`relativedelta(months=interval, day=1)`); ay sonu
  düzeltmesi `get_next_recurring_date` içinde yapılır.
- `get_next_period_date_end`: dönem sonu (`start + delta - 1 gün`, `date_end`
  ile sınırlanır).
- `get_next_recurring_date`: dönem başı/sonu + offset ile bir sonraki üretim
  tarihi. `monthlylastday` için tarih, dönem başlangıcının içinde bulunduğu ayın
  **son gününe** çekilir — ilk servis kaçmaz.
- `_get_period_end_date(process_date)`: verilen tarihin içinde bulunduğu dönemin
  sonu. Üretim artık bunu değil `next_period_date_start` üzerinden hesaplanan
  dönem sonunu kullanır (gecikmiş cron dönem atlamasın diye).

### 5.6 Üretim güvenliği (lead-time, idempotency, önizleme)

Cron akıl yürütmez, uygular: akıl yürütme giriş anında biter, üretim tek dönemde
ve tekrar edilemez biçimde yapılır.

- **Lead-time:** Üretim koşulu `due_date - lead_days <= today`. Varsayılan
  **7 gün**; `res.company.contract_generation_lead_days` (Settings → Field
  Operation, 1–30) müşteri bazında, `field.operation.contract.generation_lead_days`
  sözleşme bazında override eder (`0` = şirket değeri). `start_date` ve
  `date_order` **servis tarihinde kalır**; yalnızca belgenin oluşma anı öne alınır.
- **Idempotency:** `sale.order.contract_period_start` +
  `UNIQUE(service_contract_id, contract_period_start, partner_shipping_id)`;
  `field.operation.contract_line_id` + `UNIQUE(contract_line_id, start_date)`.
  Var olan dönem/satır atlanır, header yine de ilerler (sözleşme kilitlenmez).
  Dönemsiz eski kayıtlar (`date_order` aralığı; `contract_id + start_date +
  subject`) da tanınır.
- **Savepoint:** Her sözleşme kendi savepoint'inde üretilir; hata sözleşmenin
  chatter'ına yazılır, kitabın geri kalanı üretilmeye devam eder.
- **Önizleme:** `action_recurring_process(dry_run=True)` ve formdaki
  **Preview (nothing written)** butonu hiçbir kayıt yazmadan üretilecek
  sipariş/operasyon sayısını ve tutarı gösterir.
- **Migration:** `migrations/19.0.1.3.0/pre-migration.py` mevcut mükerrer
  belgeleri raporlar (silmez).

### 5.7 Senaryolar — Gerçek dünya örnekleri

#### Senaryo 1 — Aylık bakım sözleşmesi (Header mod)

> Müşteri X için yıllık 12 ziyaretli bakım. Her ay 1 SO + 1 saha operasyonu.

1. Sözleşme aç: `partner_id=X`, `date_start=2024-01-01`, `line_recurrence=False`.
2. Header recurring: `recurring_rule_type=monthly`, `recurring_interval=1`,
   `recurring_generation_type=beginning`.
3. Satır: `product_id=Bakım Hizmeti`, `total_service=12`, `price_unit=500`.
4. Confirm → `recurring_next_date=2024-01-01` set.
5. Cron tetikleyince (her 6 saat, `data/ir_cron_data.xml:10-11`):
   - 2024-01-01'de: SO (`order_types='invoice'`) + Field operation (draft).
     `generated_occurrences=1`.
   - 2024-02-01'de: aynı. `generated_occurrences=2`.
   - ... 2024-12-01'de: `generated_occurrences=12`, `remaining_count=0`.
6. **2025-01-01'den sonra** satır filtrelenir; üretim durur. Sözleşme confirmed
   kalır — manuel expire gerekir.

#### Senaryo 2 — Çok lokasyonlu, farklı periyotlar (Line mod)

> Müşteri Y'nin 2 şubesi var. Şube A haftalık, Şube B aylık servicing.

1. Sale order aç, `order_types='contract'`. İki servis satırı ekle:
   - Satır 1: `product=Haftalık Denetim`, `location=Şube A`
   - Satır 2: `product=Aylık Bakım`, `location=Şube B`
2. **Create Contract** → wizard.
3. Wizard satırlarında periyotları ayarla:
   - Satır 1: `recurring_rule_type=weekly`, `recurring_interval=1`
   - Satır 2: `recurring_rule_type=monthly`, `recurring_interval=1`
4. **Create Contract** → wizard `is_line_recurrence=True` tespit eder
   (`action_create_contract`), uyarı gösterir.
5. Sözleşme oluşur, `line_recurrence=True`. Kaynak SO kapatılır (`cancel`),
   `service_contract_id` link'li kalır.
6. Cron her satırı kendi `recurring_next_date`'inde işler
   (`_prepare_line_recurrence_values`):
   - Şube A için her hafta bir field.operation, her satır kendi gününde.
   - Şube B için her ay bir field.operation.
7. Her lokasyon için ayrı `order_types='service'` SO oluşur; tüm satırları
   biten lokasyon için boş SO yaratılmaz.

#### Senaryo 3 — Portal müşteri onayı (Dijital imza)

1. Müşteri portalında `/my/contracts` (`controllers/controllers.py:12`).
2. Sözleşmesini seçer (`:84-97`).
3. Detayda: lines, üretilen operasyonlar, sale order'lar, PDF indirme.
4. `/my/contract/<id>/accept` (`:119-142`) ile **dijital imza yükler** —
   sadece `state='confirmed'` ise. `signature_status=True`,
   `signature_date=now()` set (`:135-140`).
5. PDF raporda müşteri imzası gösterilir (`pdf/contract_pdf.xml` →
   `img t-if="doc.signature_file"`).

> ⚠ Portal erişim kısıtı: sadece direct `partner_id` kontrolü
> (`controllers/controllers.py:178`). Child partner (`child_of`) göremez.
> Known limitation.

### 5.8 Yakalama (catch-up) politikası ve plan tarihleri

**Politika (yazılı):** bir çalıştırma, her sözleşme için **tek dönem** üretir ve
`last_date_processed`'ı o dönemin bitişine taşır. Yani kaçırılan dönem sayısı kadar
çalıştırma gerekir; tek çalıştırmada sözleşme başına birden fazla belge üretilmez.
Üretim, servis tarihinden `generation_lead_days` gün önce başlar. Cron sıklığı bu
yüzden aynı zamanda yakalama hızıdır: ayda bir çalışan cron, üç ay geride kalan
sözleşmeyi üç çalıştırmada kapatır.

**İlk canlı çalıştırma planı (11 Kasım uzman yedeği):** 63 sözleşmenin
`recurring_next_date`'i geçmişteydi, ama üretim yalnız vadesi gelenler için belge yazar.
Bugünkü kodla aynı kitapta bir çalıştırma **10 SO + 18 operasyon** üretir (393.700 TL);
vadesi geçmiş 52 sözleşme hiçbir şey üretmez çünkü satırların `remaining_count = 0`
(işi bitmiş, hâlâ `confirmed` duran kayıtlar). Issue #54'teki **32 SO + 40 operasyon**
rakamı idempotency öncesi koda aitti (`contract_period_start` yokken aynı dönem ikinci
kez üretilebiliyordu); bugünkü beklenti 10 + 18'dir. Yani ilk çalıştırma "her şey"
değil, vadesi gelmiş sözleşmelerin ilk dönemidir. Üst sınır eklenmedi: çalıştırma
başına bir dönem kuralı zaten doğal sınırdır; daha yavaş yakalamak istenirse cron
sıklığı düşürülür.

**Plan tarihleri (`last_date_processed` / `recurring_next_date`):** bu iki alan bir
çifttir, `next = last + 1 gün`. Header modda **ikisi de düzenlenebilir** (ofis planı
elle sürer); satır bazlı moda geçildiğinde salt okunur olurlar. Elle yazılmış çiftlerde
(FOC/00005: `last=2026-03-07`, `next=2026-04-07` — aylık 1, ayın 7'si) sistem
`recurring_next_date`'i **plan** kabul eder: `19.0.1.4.0` migration'ı
`last_date_processed`'ı `next - 1 gün`e çeker (`2026-04-06`), böylece ilk üretim servis
gününü kaydırmaz (7 → 8 hatası). Uzman kopyasında 11 header + 34 aktif satır taşındı;
`remaining_count=0` olan 31 satıra dokunulmadı. Header ve satır `recurring_next_date`
değerlerinin tamamı **birebir korundu** (fingerprint aynı).

Migration bu hizalamayı yalnız `recurring_generation_type = 'beginning'` ve
`monthlylastday` dışındaki kurallar için yapar. `end` tipinde olay dönem sonunda
olduğu için çift `next = last + 1` değildir; `last`'ı `next - 1`'e çekmek planı bir
dönem ileri taşır (ölçüm: aylık/1/end çiftinde `next` `2026-05-01` → `2026-06-01`).
`monthlylastday`'de olay tarihi korunur ama dönem penceresi ay sonuna kayar ve mevcut
`contract_period_start` ile eşleşmez; ikisi de hizalanmaz.

**Müşteri verisiyle doğrulama:** yedeğin geçici kopyasında, müşteri modülleri yüklüyken
upgrade 0 ERROR ile bitti. Dry-run 10 SO + 18 operasyon (393.700 TL) ve hatasız sonuç verdi;
gerçek tek çalıştırma aynı 10 + 18 kaydı üretti (SO 613 → 623, operasyon 576 → 594).
FOC/00005 yeni periyoda `recurring_next_date=2026-05-07` ile geçti; servis günü 7'de kaldı.
Bu işlemler yalnız test kopyasında yapıldı, kaynak `t_uzman50` değiştirilmedi.

---

## 6. Satış ↔ Sözleşme ↔ Field Operation Zinciri

Üçlü link ilişkisi:

```
   sale.order                          field.operation.contract
   ┌──────────────┐                    ┌──────────────────────┐
   │              │   service_         │                      │
   │ order_types  │   contract_id      │  name (FOC/00001)    │
   │ ='contract'  │◀───────────────────│  partner_id          │
   │   or 'invoice'│                    │  state               │
   │   or 'service'│                    │  line_recurrence     │
   │              │                    │  contract_line_ids ──┼──┐
   │ state='cancel'│                    │                      │  │
   └──────┬───────┘                    └──────────┬───────────┘  │
          │                                       │              │
          │ sale_id                               │ contract_id  │
          │                                       │              │
          ▼                                       ▼              ▼
   field.operation                          field.operation    field.operation
   ┌──────────────┐                          ┌─────────────┐   ┌─────────────┐
   │ start_date   │                          │ product_id  │   │ product_id  │
   │ state='draft'│                          │ total_      │   │ total_      │
   │ location_id  │                          │  service    │   │  service    │
   └──────────────┘                          │ remaining_  │   │ remaining_  │
                                             │  count      │   │  count      │
                                             └─────────────┘   └─────────────┘
```

> Kaynak teklif (`order_types='contract'`) **açıkken** (draft/sent/cancel)
> `generated_sale_ids` / `sale_count` ve portal listesinden gizlenir. Teklif
> **onaylandığında** (`state='sale'`) gerçek bir sipariştir ve butonda/portalda görünür
> (issue #54, madde 1: uzman kitabında 56 onaylı + 8 dönüştürülmüş sipariş bu yüzden
> erişilemiyordu). Üretilen dönemsel
> siparişler `draft` durumunda yaratılır.

### Alan linkleri

| Kaynak | Hedef | Alan | Dosya |
|---|---|---|---|
| `sale.order` | `field.operation.contract` | `service_contract_id` | `models/sale_order.py` → `service_contract_id` |
| `field.operation` | `field.operation.contract` | `contract_id` | `models/field_operation.py` → `contract_id` |
| `field.operation` | `sale.order` | `sale_id` | `_recurring_create_sale_ops` içinde set edilir |
| `field.operation.contract.line` | `field.operation.contract` | `contract_id` | `models/field_operation_contract_line.py` → `contract_id` |

### Smart butonlar

- **Sözleşme → Operasyonlar**: `service_count` (`views/field_operation_contract_view.xml`)
- **Sözleşme → Satışlar**: `sale_count` — `order_types='contract'` kaynak teklifi
  saymaz (`generated_sale_ids` alan domain'i + `action_view_sales` domain'i)
- **Partner → Sözleşmeler**: `service_contract_count` (`views/res_partner_view.xml`)
- **Sale order → Sözleşme**: `service_contract_count` (`views/sale_order_view.xml`)
- **Field operation → Sözleşme**: `service_contract_count` (`views/field_operation_view.xml`)

---

## 7. PDF Raporu

**Template:** `pdf/contract_pdf.xml` → `report_field_operation_contract_document`

- **Model:** `field.operation.contract`
- **Tip:** `qweb-pdf`
- **Layout:** `web.external_layout`
- **Print name:** `'Contract - %s' % object.name`

### İçerik (Türkçe sözleşme formatı)

- **Madde 1 — Taraflar**: Satıcı/Alıcı, tarih aralığı (taraflar tablosu)
- **Madde 2 — Hizmetin Tanımı**: lines tablosu (Hizmet, Adet, Birim Fiyat,
  İndirim, Vergi, Tutar) (hizmet tablosu)
- **Toplamlar**: Ara Toplam, Toplam Vergi, Genel Toplam (toplam bloğu)
- **Sözleşme Şartları + Açıklama** (`contract_terms` / `description` alanları)
- **İmza blokları**:
  - SATICI FİRMA → `doc.company_id.pdf_signature` ile **şirket imzası otomatik**
    (`img t-if="doc.company_id.pdf_signature"`). Şirket formunda bu alan
    doldurulmalı (`models/res_company.py` → `pdf_signature`).
  - ALICI FİRMA → müşteri imzası (`signature_file`), sadece portal'da yüklenmişse
    (`img t-if="doc.signature_file"`).

---

## 8. Bilinen Sınırlamalar / Teknik Borç

Bu bölüm, modülün production'da dikkat edilmesi gereken noktalarını listeler.
Hepsi **kod tespitidir**, çalışma zamanında doğrulanmamış bazıları test ile
teyit edilmelidir.

### P0 — Olası bug

1. ~~Section/note satırlarında `date_start` required riski~~ — **çözüldü.**
   Satır `create()`'i `display_type` taşıyan kayıtlar için `date_start`'ı sözleşme
   başlangıcına (yoksa bugüne) düşürür;
   `test_action_create_contract_with_section_line` bunu kapsar.

2. **`test_wizard_line_name_fallback` zayıf assert.** `description_sale`
   boş bir üründe `get_product_multiline_description_sale()` ile `display_name`
   aynı string'e düşer, bu yüzden test iki davranışı ayırt etmez. Açıklaması dolu
   bir ürünle assert edilirse gerçek guard olur.

### P1 — Fonksiyonel gap

3. **`action_renew` yok.** Eski `to_renew` state'i kaldırıldı
   (`test_to_renew_state_removed`); yenileme akışı hâlâ elle yürütülür.

4. **Otomatik expire yok.** `date_end` geçse bile sözleşme `confirmed` kalır.
   Sadece manuel `action_expire` butonu.

5. ~~Confirmed state'te alan kilidi yok~~ — **çözüldü.** Form view'de header
   alanları ve satır listesi `readonly="state != 'draft'"`; onaydan sonra
   düzenlenemez.

6. ~~Multi-company izolasyonu yok~~ — **çözüldü.** `security/security.xml`
   şirket bazlı iki kural (`rule_field_operation_contract_company`,
   `rule_field_operation_contract_line_company`) ve portal müşterisi için bir kural
   (`rule_field_operation_contract_portal`) taşır.

7. **Sözleşme satırı vergisi üretilen sale.order satırına taşınmıyor.**
   Wizard satırı `tax_id` taşıyor ve `action_create_contract` vergileri sözleşme
   satırına kopyalıyor (`test_action_create_contract_maps_taxes`), ancak
   `_prepare_header_recurrence_values` / `_prepare_line_recurrence_values`
   içindeki `order_line` vals'lerinde `tax_ids` geçmiyor: üretilen satır ürünün
   varsayılan vergileriyle oluşur, sözleşme satırında elle değiştirilen vergi
   taşınmaz.

### P2 — İyileştirme fırsatları

8. **Portal child partner erişimi yok.** `_document_check_access`
   (`controllers/controllers.py:178`) sadece direct `partner_id` kontrol eder.
   `commercial_partner_id`/`child_of` değil. Alt partnerlar sözleşmeyi göremez.

9. **Dead fields wizard line.** `total_occurrences` ve `period_calculation`
    alanları wizard line modelinde tanımlı ama `action_create_contract`'ta hiç
    kullanılmıyor.

10. **Hidden gruplar kullanılmıyor.** `field_operation.group_field_operation_recurring`
    ve `group_field_operation_signature` saha modülünde tanımlı ama contract
    modülünde referans yok.

11. **Saha kullanıcısı için kişiselleştirme yok.** `security.xml` yalnızca
    şirket ve portal kurallarını taşır; "sadece kendi sözleşmelerini görsün"
    (kullanıcı bazlı) bir kural istenirse elle eklenmeli.

12. **Test'lerin çoğu `@tagged` değil.** `post_install` tagged olanlar:
    `test_recurring_process.py` (`TestRecurringProcess`) ve
    `test_contract_review_fixes.py` (`TestContractPortalPdf`). Diğerleri
    `at_install`; bu yüzden `-i` tek başına o iki sınıfı toplamaz, `-u` gerekir.

---

## 9. Test Kapsamı

**Toplam 82 test, 8 dosya.** `tests/__init__.py` hepsini yükler.

| Dosya | Class | Test sayısı | Odak |
|---|---|---|---|
| `test_contract.py` | `TestContract` | 10 | Sequence, confirm hata/başarı, toplam tutar, kalan gün, view action'ları, state geçişleri |
| `test_contract_line.py` | `TestContractLine` | 6 | `remaining_count`, subtotal, varsayılan lokasyon, `available_location_ids`, stored subtotal |
| `test_recurring_mixin.py` | `TestRecurringMixin` | 15 | `get_relative_delta` varyasyonları, `next_period_date_start`, default offset, `get_next_recurring_date` (monthlylastday dahil), `remaining_count <= 0` → next_date False |
| `test_recurring_process.py` | `TestRecurringProcess` (`post_install`) | 6 | SO üretimi, field.operation üretimi, sayaç güncellemesi, **multi-location grouping** (3 satır 2 lokasyon → 2 SO), gelecek tarihte no-op, cron çalıştırma |
| `test_line_recurrence.py` | `TestLineRecurrence` | 4 | Karışık periyot/lokasyon, gecikmiş cron dönem ilerletme, `end` üretim tipi, `monthlylastday` |
| `test_generation_safety.py` | `TestGenerationSafety` | 9 | Lead-time (şirket/sözleşme), idempotency (dönem/satır + eski kayıt), savepoint izolasyonu, dry-run |
| `test_sale_order_contract_wizard.py` | `TestSaleOrderContractWizard` | 15 | `default_get`, `_validate_lines`, `action_create_contract`, kaynak teklifin kapatılması ve confirm guard'ı, vergi eşlemesi, section satırı, name fallback, açılan action |
| `test_contract_review_fixes.py` | `ContractReviewFixCase`, `TestWizardGuards`, `RecurrenceConstraints`, `HeaderRecurrenceFixes`, `RecurringNextDateCompute`, `ContractLifecycleGuards`, `SignatureAndSchemaCleanup`, `TestContractPortalPdf` (`post_install`) | 17 | Önceki inceleme notlarının guard'ları: rule/ACL, header recurrence, `to_renew` temizliği, portal PDF 200 |

### Çalıştırma

İki faz gerekir: `post_install` tagged sınıflar `-i` sırasında toplanmaz.

```bash
# 1) kurulum
/home/tate/odoo/v19/venv/bin/python /home/tate/odoo/v19/odoo/odoo-bin \
  -c /home/tate/odoo/v19/v19.conf -d <db> \
  --addons-path=<core addons>,<repo kökü> --without-demo=True \
  -i field_operation_contract --stop-after-init

# 2) testler
/home/tate/odoo/v19/venv/bin/python /home/tate/odoo/v19/odoo/odoo-bin \
  -c /home/tate/odoo/v19/v19.conf -d <db> \
  --addons-path=<core addons>,<repo kökü> --without-demo=True \
  -u field_operation_contract --test-tags=/field_operation_contract --stop-after-init
```

Tek bir test için sınıf/metot adı verilir (dosya yolu tag'i yok):

```bash
--test-tags=/field_operation_contract:TestLineRecurrence.test_mixed_periods_and_locations
```

> `/home/tate/odoo/venv-19/bin/python` bu host'ta v19 bağımlılıklarını taşımaz
> (`babel` yok); `v19/venv` kullanılmalı. Son doğrulanan sonuç: **73 test,
> 0 failed, 0 error** — hem temiz kurulumda hem `19.0.1.1.0 → 19.0.1.2.0`
> yükseltmesinde.

### Boşluklar (test planı için)

- **Section/note satırı senaryosu** — kapsandı
  (`test_action_create_contract_with_section_line`).
- **`is_line_recurrence` auto-detection** — farklı periyotlarla line moduna geçiş.
- **Wizard warning mesajı** — `is_line_recurrence=True` iken `result['warning']`.
- **Kaynak teklif kapanışı** — `test_action_create_contract_links_sale_order` ve
  `test_converted_quotation_cannot_be_confirmed`.
- **Sözleşme satırı vergisinin üretilen sale.order satırına taşınması** —
  kapsanmıyor ([Bölüm 8 #7](#p1--fonksiyonel-gap)).
- **Multi-company** — şirket kuralı var ama testi yok.
- **ACL** — `service_group_user` dışı kullanıcı wizard çalıştıramaz.

---

## 10. Geliştirici Notları

### Sequence

- `data/ir_sequence_data.xml:4-10`: `FOC/` prefix, padding 5, company-independent.
- `create()` override (`models/field_operation_contract.py` → `create`) `name == "/"`
  ise `ir.sequence.next_by_code("field.operation.contract")` çağırır. Try/catch
  yok; sequence yoksa fallback `"New"`.

### Bulk create pattern (`_recurring_create_sale_ops`)

3 fazlı tasarım performans için:

1. **Hazırlık** — DB yazma olmadan tüm vals toplanır (`_prepare_recurrence_values`)
2. **Toplu oluşturma** — Önce sale.order'lar bulk create, sonra field.operation'lar
3. **Takip** — generated_occurrences / recurring_next_date güncellemeleri ve log

Multi-company aware: contract'ları `company_id`'ye göre gruplar, her şirket için
`with_company` context'i ile işler.

### Mixin (OCA Contract'tan ilham)

`models/service_contract_recurring_mixin.py` — abstract model, hem sözleşme
header'ında hem satırında inherit. Tarih hesaplama (`get_relative_delta`,
`get_next_period_date_end`, `get_next_recurring_date`) OCA Contract modülünün
mantığını takip eder.

### Migration notu

`migrations/19.0.1.0.1/post-migration.py` — `remaining_count > 1_000_000` olan
satırları düzeltir (eski mixin default değeri `10**9`'dan kaynaklı bug fix).
Ayrıca `migrations/19.0.1.0.8/pre-migration.py` ve `migrations/19.0.1.0.9/` var.

### Cron

`data/ir_cron_data.xml:4-14` — her 6 saatte bir `action_recurring_process()`.
`noupdate="1"` ile geliştirici değiştirebilir.

### Kaynak dosya haritası

```
field_operation_contract/
├── __manifest__.py
├── models/
│   ├── field_operation_contract.py        # Ana model + recurring metodları
│   ├── field_operation_contract_line.py   # Satır + create() override
│   ├── field_operation_contract_tag.py
│   ├── field_operation.py                 # field.operation'a contract_id ekle
│   ├── sale_order.py                      # sale.order'a order_types/service_contract_id ekle
│   ├── res_partner.py                     # smart button
│   ├── res_company.py                     # pdf_signature
│   └── service_contract_recurring_mixin.py
├── wizard/
│   ├── sale_order_to_contract_wizard.py
│   └── sale_order_to_contract_wizard_view.xml
├── views/
│   ├── field_operation_contract_view.xml
│   ├── field_operation_contract_tag_view.xml
│   ├── field_operation_view.xml           # field.operation form inherit
│   ├── sale_order_view.xml                # sale.order header buton + smart button
│   └── res_partner_view.xml
├── controllers/
│   └── controllers.py                     # Portal route'ları
├── template/
│   ├── portal_my_contracts.xml
│   └── portal_contract_page.xml
├── pdf/
│   └── contract_pdf.xml
├── data/
│   ├── ir_sequence_data.xml               # FOC/ sequence
│   └── ir_cron_data.xml                   # Her 6 saat recurring
├── security/
│   ├── ir.model.access.csv
│   └── security.xml                       # BOŞ
├── migrations/
│   └── 19.0.1.0.1/post-migration.py
└── tests/
    ├── __init__.py
    ├── test_contract.py
    ├── test_contract_line.py
    ├── test_recurring_mixin.py
    ├── test_recurring_process.py
    ├── test_line_recurrence.py
    ├── test_generation_safety.py
    ├── test_sale_order_contract_wizard.py
    └── test_contract_review_fixes.py
```

---

## Lisans

AGPL-3 — `__manifest__.py:25`. Yazar: **Softteknik Bilişim** (`:21`),
[https://softteknik.com](https://softteknik.com).
