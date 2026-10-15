# Field Operation Contract Management

> Saha (Field Operation) servisi için **recurring (yinelenen) sözleşme yönetimi**.
> Sales ↔ Invoicing ↔ Field Service arasında köprü kurar. Softteknik Bilişim,
> Odoo 19, AGPL-3, sürüm `19.0.1.0.10`.

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

### Bağımlılıklar (`__manifest__.py:26-30`)

| Modül | Sağladığı |
|---|---|
| `field_operation` | `field.operation` modeli, `field.operation.type` (servis tipi), gruplar (`service_group_user`, `service_group_manager`) |
| `field_operation_sale` | `sale.order.order_types` alanı (`service`/`stock`) |
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
| `remaining_count` | `max(0, total_service - generated_occurrences)` — kalan adet (`field_operation_contract_line.py:51-54`) |
| `line_recurrence` | True → her satır kendi periyodunda; False → header periyodu geçerli |

---

## 2. Roller ve Güvenlik

### Grup hiyerarşisi (`apps/saha/field_operation/security/res_groups.xml`)

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
(`views/field_operation_contract_view.xml:14`).

### ⚠ Multi-company kısıtı YOK

`security/security.xml` boş (`<odoo/>`); hiçbir `ir.rule` yok. Yani
`company_id` alanı görünür ve set edilebilir ama **farklı şirketlerin
sözleşmelerini görmeyi engelleyen bir kural yok**. Known limitation
(bkz. [Bölüm 8](#8-bilinen-sınırlamalar--teknik-borç)).

---

## 3. Kontrat Oluşturma — 2 Senaryo

Sözleşme 2 farklı yoldan oluşturulabilir:

| Senaryo | Tetikleyici | Araç | Kaynak kod |
|---|---|---|---|
| **A. Manuel** | Saha menüsü → Contracts → New | Direkt form | `views/field_operation_contract_view.xml:206` |
| **B. Satıştan** | `sale.order` `order_types='contract'` → **Create Contract** butonu | Wizard | `wizard/sale_order_to_contract_wizard.py` |

### Senaryo A — Manuel Olarak Sözleşme Açmak

En yaygın yol. Ofis kullanıcısı doğrudan sözleşme oluşturur.

**Adımlar:**

1. **Saha → Contracts → New** (`action_field_operation_contract`,
   `views/field_operation_contract_view.xml:206-215`).
2. **Zorunlu alanları doldur:**
   - `partner_id` — müşteri (required, `models/field_operation_contract.py:58`)
   - `date_start` — başlangıç (required, default bugün, `:19`)
   - `service_type_ids` — servis tipleri (required M2M, `:62`)
3. **Recurring modu seç** (sol grup):
   - `line_recurrence = False` (varsayılan) → **header bazlı**: tüm satırlar ortak
     periyotla çalışır. Sağdaki `recurring_rule_type`, `recurring_interval`,
     `recurring_generation_type`, `recurring_next_date` alanları görünür.
   - `line_recurrence = True` → **satır bazlı**: her satırın kendi periyodu.
     Sağdaki header recurring alanları gizlenir (`views/field_operation_contract_view.xml:71-79`),
     satır bazlı alanlar list view'da açılır (`:108-121`).
4. **Satırları ekle** ("Services & Products" sekmesi):
   - `product_id` (yalnızca `type='service'`, `field_operation_contract_line.py:41-42`)
   - `total_service` — söz verilen toplam servis adedi (örn. 12)
   - `price_unit`, `discount`
   - Satır bazlı modda: `recurring_rule_type`, `recurring_interval`,
     `recurring_next_date` her satır için ayrı girilir
5. **Confirm** butonuna bas → `state='confirmed'`. Header modda boşsa
   `recurring_next_date = date_start` set edilir (`field_operation_contract.py:473-474`).
6. Artık sözleşme cron tarafından işlenmeye hazır.

**Sözleşme no** otomatik üretilir: `FOC/00001`, `FOC/00002`, ...
(`data/ir_sequence_data.xml:4-10`, `models/field_operation_contract.py:454-459`).

> **Not — `name` fallback davranışı:** Satır `name` boşsa, `contract_line.create()`
> override'ı ürünün açıklamasını yazar (`field_operation_contract_line.py:97-100`,
> `get_product_multiline_description_sale()`). Ürün de yoksa `"Service Line"`.

### Senaryo B — Satış Siparişinden Sözleşme Oluşturmak

Bir satış siparişini recurring sözleşmeye dönüştürür. Tipik kullanım: müşteri
 ilk yıl için teklif alınca, teklif onaylanınca sözleşmeye çevrilir.

**Adımlar:**

1. **Satış siparişi aç**, `order_types = 'contract'` seç.
   - `order_types` alanı `field_operation_sale` modülünde tanımlı
     (`apps/saha/field_operation_sale/models/sale_order.py:12`), contract modülü
     `'contract'` ve `'invoice'` seçeneklerini ekler
     (`models/sale_order.py:10`).
2. **Create Contract** butonu header'da görünür — sadece `order_types='contract'`
   VE `service_contract_id` boşsa (`views/sale_order_view.xml:10-15`).
3. **Wizard açılır** (`sale.order.contract.wizard`). `default_get` otomatik:
   - Sale order'dan `partner_id`, `company_id`, `date_start=today`,
     `date_end=today+1y` (`wizard/sale_order_to_contract_wizard.py:70-77`).
   - Sadece **service product** satırları wizard'a kopyalanır; `consu`/`product`
     tipler atlanır (`:37`).
   - `service_type_ids` ürünlerin `service_type_id` alanından toplanır (`:48-49`).
   - Her satıra varsayılan: `recurring_interval=1`, `recurring_rule_type='monthly'`,
     `recurring_next_date=today` (`:61-63`).
4. Kullanıcı satırlarda **lokasyon**, **periyot**, **adet** düzeltebilir.
5. **Create Contract** → `action_create_contract` (`wizard/sale_order_to_contract_wizard.py:83-178`):
   - **Otomatik mod kararı** (`:90-102`): Eğer satırların `recurring_rule_type`,
     `recurring_interval` veya `recurring_next_date` değerlerinden herhangi biri
     farklıysa `line_recurrence=True` set edilir. Kullanıcıya uyarı gösterilir.
   - Sözleşme oluşturulur; **sale.order** `state='sent'` yapılır ve
     `service_contract_id` ile sözleşmeye bağlanır (`:153-156`).
   - Dönüş değeri: sözleşme formunu açan `ir.actions.act_window`.

**Satır eşlemesi (wizard → sözleşme satırı)**, `wizard/sale_order_to_contract_wizard.py:117-136`:

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

> ⚠ **Vergi (tax) eşlemesi yok.** Wizard'da `tax_id` alanı yok; sözleşme satırı
> vergisiz oluşur. Known limitation (bkz. [Bölüm 8](#8-bilinen-sınırlamalar--teknik-borç)).

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

> ⚠ `to_renew` state'i tanımlı (`field_operation_contract.py:75`) ama **hiçbir
> action/cron bu state'e geçmez** (dead code). `action_renew` da implement
> edilmemiş. Known limitation.

### State geçiş metodları

| Metot | Dosya:Line | Koşul / Yan etki |
|---|---|---|
| `action_confirm` | `models/field_operation_contract.py:469-485` | Line yoksa `UserError`. Header modda `recurring_next_date` boşsa `date_start` set. `signature_date = now()`. |
| `action_cancel` | `:487-488` | Koşulsuz `state='cancel'`. |
| `action_set_to_draft` | `:490-491` | Koşulsuz `state='draft'`. |
| `action_expire` | `:493-494` | Koşulsuz `state='expired'`. **Sadece manuel buton.** |
| `action_renew` | — | **Yok** (planlanmamış). |

### ⚠ Otomatik expire YOK

`date_end` geçse bile sözleşme `confirmed` kalır. Cron
(`data/ir_cron_data.xml:4-14`) sadece `action_recurring_process`'i çağırır,
`expired`'e düşürmez. Domain filtresi (`_get_contracts_to_process_domain`,
`:143-154`) `date_end >= today` şartı arar ama **uygunsuz sözleşmeleri
expire etmez**, sadece recurring işlemesini atlar.

Manuel `action_expire` butonu formda görünür (statusbar'da `expired` gösteriliyor).

### Alan kilidi

View'de **confirmed state için per-state readonly yok**. Yani confirmed
sonrası header alanları hâlâ düzenlenebilir. Known limitation.

---

## 5. Recurring (Yinelenen) Servis Takibi

Modülün kalbi burası. İki moddan biri seçilir; her mod farklı üretim mantığı
çalıştırır.

### 5.1 İki mod karşılaştırması

| Özellik | Header-based (`line_recurrence=False`) | Line-based (`line_recurrence=True`) |
|---|---|---|
| **Tetikleme** | Sözleşmenin `recurring_next_date`'i | Her satırın kendi `recurring_next_date`'i |
| **Hazırlama metodu** | `_prepare_header_recurrence_values` (`:256-350`) | `_prepare_line_recurrence_values` (`:352-442`) |
| **Üretilen sale.order `order_types`** | `'invoice'` (`:289`) | `'service'` (`:385`) |
| **Field operation tarihi** | `process_date` (bugün) (`:313-324`) | `line.recurring_next_date` (`:414`) |
| **Tarihi kim ilerletir** | Sözleşme header'ı | Her satır ayrı ayrı |
| **Kullanım** | Tek tip servis, tek periyot | Çok lokasyon/farklı periyotlar |

### 5.2 Üretim akışı (cron → records)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Cron (her 6 saat)        data/ir_cron_data.xml:4-14                │
│  ↓                                                                   │
│  action_recurring_process()      models/field_operation_contract    │
│                                    .py:156-177                       │
│  ↓                                                                   │
│  Domain: state=confirmed, active=True,                              │
│          date_end IS NULL OR date_end >= today      (:143-154)      │
│  ↓                                                                   │
│  Şirketlere göre grupla, with_company context'i      (:170-174)     │
│  ↓                                                                   │
│  _recurring_create_sale_ops()      (:179-251)                       │
│  │  3 fazlı bulk pattern:                                           │
│  │                                                                   │
│  │  Faz 1 — Hazırlık (DB yazma yok)        (:190-213)               │
│  │  ├─ Her contract için mod seçimi:                                │
│  │  │   line_recurrence? → _prepare_line_recurrence_values          │
│  │  │   else            → _prepare_header_recurrence_values         │
│  │  ├─ Lokasyon bazlı gruplama (_group_lines_by_location, :444-449) │
│  │  └─ unique_key ile SO ↔ FieldOp eşleştirme                       │
│  │                                                                   │
│  │  Faz 2 — Toplu oluşturma                  (:218-233)              │
│  │  ├─ Tüm sale.order'lar BULK create         (:220)                │
│  │  ├─ key_to_so_id mapping                   (:223-226)            │
│  │  └─ field.operation'lar create + sale_id   (:229-233)            │
│  │                                                                   │
│  │  Faz 3 — Takip güncellemeleri             (:235-249)              │
│  │  ├─ generated_occurrences += 1            (:326-329 / :434-437)  │
│  │  ├─ recurring_next_date ilerlet           (:333-348 / :430-432)  │
│  │  └─ message_post ile log                                         │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.3 Üretilen kayıt sayısı (örnek)

Bir sözleşmede **3 servis satırı**, **2 farklı lokasyon** varsa ve bugün
processing tarihine geldiyse:

- **Header mod**: 2 sale.order (loksasyon başına 1) + 3 field.operation
  (satır başına 1, hepsi bugünün tarihinde)
- **Line mod**: 2 sale.order + 3 field.operation (ama her field.operation
  kendi satırının `recurring_next_date`'inde — farklı günlerde olabilir)

### 5.4 Servis adedinin tükenmesi

```
total_service         = 12      (sözleşmede söz verilen)
generated_occurrences = 0  → 1 → 2 → ... → 12     (her periyotta artar)
remaining_count       = 12 → 11 → 10 → ... → 0    (compute, :51-54)
```

`remaining_count = 0` olduğunda:

- Satır recurring domain'inde filtrelenir (`_prepare_header_recurrence_values:265`,
  `_prepare_line_recurrence_values:363`).
- Artık o satır için SO/FieldOp üretilmez.
- **Sözleşme `confirmed` kalır** — otomatik expire yok. Manuel `action_expire`
  gereklidir.

### 5.5 Tarih hesaplama (mixin)

`models/service_contract_recurring_mixin.py` OCA Contract'tan ilhamla:

- `_get_default_recurring_offset` (`:205-210`): `beginning`/`monthlylastday` → 0,
  `end` → 1.
- `get_relative_delta` (`:130-147`): `relativedelta` factory; `monthlylastday`
  ayın son günü.
- `get_next_period_date_end` (`:149-178`): dönem sonu.
- `get_next_recurring_date` (`:180-203`): dönem başı/sonu + offset ile
  bir sonraki üretim tarihi.

### 5.6 Senaryolar — Gerçek dünya örnekleri

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
   (`wizard/sale_order_to_contract_wizard.py:97-102`), uyarı gösterir
   (`:168-176`).
5. Sözleşme oluşur, `line_recurrence=True`. SO `state='sent'`,
   `service_contract_id` link'li.
6. Cron her satırı kendi `recurring_next_date`'inde işler
   (`_prepare_line_recurrence_values`, `:352-442`):
   - Şube A için her hafta bir field.operation, her satır kendi gününde.
   - Şube B için her ay bir field.operation.
7. Her lokasyon için ayrı `order_types='service'` SO oluşur (`:385`).

#### Senaryo 3 — Portal müşteri onayı (Dijital imza)

1. Müşteri portalında `/my/contracts` (`controllers/controllers.py:12`).
2. Sözleşmesini seçer (`:84-97`).
3. Detayda: lines, üretilen operasyonlar, sale order'lar, PDF indirme.
4. `/my/contract/<id>/accept` (`:119-142`) ile **dijital imza yükler** —
   sadece `state='confirmed'` ise. `signature_status=True`,
   `signature_date=now()` set (`:135-140`).
5. PDF raporda müşteri imzası gösterilir (`pdf/contract_pdf.xml:105-107`).

> ⚠ Portal erişim kısıtı: sadece direct `partner_id` kontrolü
> (`controllers/controllers.py:178`). Child partner (`child_of`) göremez.
> Known limitation.

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
   │ state='sent' │                    │                      │  │
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

### Alan linkleri

| Kaynak | Hedef | Alan | Dosya |
|---|---|---|---|
| `sale.order` | `field.operation.contract` | `service_contract_id` | `models/sale_order.py:8` |
| `field.operation` | `field.operation.contract` | `contract_id` | `models/field_operation.py:10` |
| `field.operation` | `sale.order` | `sale_id` | `_recurring_create_sale_ops` içinde set (`field_operation_contract.py:229-231`) |
| `field.operation.contract.line` | `field.operation.contract` | `contract_id` | `field_operation_contract_line.py:43-44` |

### Smart butonlar

- **Sözleşme → Operasyonlar**: `service_count` (`views/field_operation_contract_view.xml:26-34`)
- **Sözleşme → Satışlar**: `sale_count` (`:36-44`)
- **Partner → Sözleşmeler**: `service_contract_count` (`views/res_partner_view.xml:3-14`)
- **Sale order → Sözleşme**: `service_contract_count` (`views/sale_order_view.xml:17-22`)
- **Field operation → Sözleşme**: `service_contract_count` (`views/field_operation_view.xml:8-13`)

---

## 7. PDF Raporu

**Template:** `pdf/contract_pdf.xml` → `report_field_operation_contract_document`

- **Model:** `field.operation.contract`
- **Tip:** `qweb-pdf`
- **Layout:** `web.external_layout`
- **Print name:** `'Contract - %s' % object.name`

### İçerik (Türkçe sözleşme formatı)

- **Madde 1 — Taraflar**: Satıcı/Alıcı, tarih aralığı (`:14-22`)
- **Madde 2 — Hizmetin Tanımı**: lines tablosu (Hizmet, Adet, Birim Fiyat,
  İndirim, Vergi, Tutar) (`:24-83`)
- **Toplamlar**: Ara Toplam, Toplam Vergi, Genel Toplam (`:85-109`)
- **Sözleşme Şartları + Açıklama** (`:111-118`)
- **İmza blokları**:
  - SATICI FİRMA → `doc.company_id.pdf_signature` ile **şirket imzası otomatik**
    (`:129-131`). Şirket formunda bu alan doldurulmalı (`models/res_company.py:7-9`).
  - ALICI FİRMA → müşteri imzası (`signature_file`), sadece portal'da yüklenmişse
    (`:138-150`).

---

## 8. Bilinen Sınırlamalar / Teknik Borç

Bu bölüm, modülün production'da dikkat edilmesi gereken noktalarını listeler.
Hepsi **kod tespitidir**, çalışma zamanında doğrulanmamış bazıları test ile
teyit edilmelidir.

### P0 — Olası bug

1. **Section/note satırlarında `date_start` required riski.** Wizard
   (`wizard/sale_order_to_contract_wizard.py:108-116`) section/note satırları için
   yalnızca `name`/`display_type`/`sequence` geçirir. Ama contract line modelinde
   `date_start = fields.Date(required=True)` (`field_operation_contract_line.py:27`).
   `create()` override'ı (`:96`) sadece `name`/`location_id` fallback atlar,
   required check'i atlatmaz. **Test edilmeli** — patlar mı, yoksa Odoo display_type
   için required'ı mı atlıyor?

2. **Mevcut `test_wizard_line_name_fallback` testi yanlış assert ediyor.**
   `tests/test_sale_order_contract_wizard.py:238` `display_name` assert ediyor;
   ama `contract_line.create()` `get_product_multiline_description_sale()`
   kullanır (`field_operation_contract_line.py:100`). Test düzeltilmeli.

### P1 — Fonksiyonel gap

3. **`to_renew` state'i dead code.** Tanımlı (`field_operation_contract.py:75`)
   ama hiçbir action/cron bu state'e geçmez. `action_renew` yok.

4. **Otomatik expire yok.** `date_end` geçse bile sözleşme `confirmed` kalır.
   Sadece manuel `action_expire` butonu.

5. **Confirmed state'te alan kilidi yok.** View'de per-state readonly yok
   (`views/field_operation_contract_view.xml`). Sözleşme onaylandıktan sonra
   bile header alanları düzenlenebilir.

6. **Multi-company izolasyonu yok.** `security/security.xml` boş; `ir.rule` yok.
   Farklı şirketlerin sözleşmelerini görmeyi engelleyen kural yok. Sadece
   `company_id` alanı `groups="base.group_multi_company"` ile görünür.

7. **Wizard vergi (tax) eşlemesi yok.** Wizard'da `tax_id` alanı yok; sözleşme
   satırı vergisiz oluşur. Üretilen sale.order satırında da vergi olmaz
   (wizard üzerinden gelen akışta).

### P2 — İyileştirme fırsatları

8. **Portal child partner erişimi yok.** `_document_check_access`
   (`controllers/controllers.py:178`) sadece direct `partner_id` kontrol eder.
   `commercial_partner_id`/`child_of` değil. Alt partnerlar sözleşmeyi göremez.

9. **Dead fields wizard line.** `total_occurrences` ve `period_calculation`
    alanları wizard line'da (`wizard/sale_order_to_contract_wizard.py:191, 220-224`)
    tanımlı ama `action_create_contract`'ta hiç kullanılmıyor.

10. **Hidden gruplar kullanılmıyor.** `field_operation.group_field_operation_recurring`
    ve `group_field_operation_signature` saha modülünde tanımlı ama contract
    modülünde referans yok.

11. **`security.xml` boş.** Hiç record rule yok; "kendi sözleşmelerini görme"
    gibi bir kişiselleştirme istenirse elle eklenmeli.

12. **Test'lerin çoğu `@tagged` değil.** Sadece `test_recurring_process.py`
    `post_install` tagged. Diğerleri `at_install` (hızlı ama install sırasında).

---

## 9. Test Kapsamı

**Toplam ~46 test metodu, 5 dosya.** `tests/__init__.py` hepsini yükler.

| Dosya | Class | Test sayısı | Odak |
|---|---|---|---|
| `test_contract.py` | `TestContract` | 9 | Sequence (`:27`), confirm error/success (`:36`, `:45`), total amount (`:65`), rest days (`:87`, `:98`), view actions (`:108`, `:118`), state transitions (`:128`) |
| `test_contract_line.py` | `TestContractLine` | 6 | `remaining_count` (`:27`, `:39`), subtotal (`:51`), default location (`:63`), `available_location_ids` (`:80`), stored subtotal (`:111`) |
| `test_recurring_mixin.py` | `TestRecurringMixin` | 13 | `get_relative_delta` (7 varyasyon, `:34-68`), `next_period_date_start` (`:70`), default offset (`:81-96`), `get_next_recurring_date` (`:98-122`), `remaining_count <= 0` → next_date False (`:124`) |
| `test_recurring_process.py` | `TestRecurringProcess` (`@tagged('post_install', '-at_install')`) | 6 | SO üretimi (`:47`), field.operation üretimi (`:55`), counter update (`:63`), **multi-location grouping** (`:72` — 3 satır 2 lokasyon → 2 SO), no-op when future date (`:131`), cron execution (`:139`) |
| `test_sale_order_contract_wizard.py` | `TestSaleOrderContractWizard` | 12 | `default_get` (`:59`, `:75`, `:90`, `:108`, `:117`), `action_create_contract` (`:129`, `:151`, `:178`, `:191`, `:212`), name fallback (`:225`), open action (`:240`) |

### Çalıştırma

```bash
/home/tate/odoo/venv-19/bin/python3 /home/tate/odoo/v19/odoo/odoo-bin \
  -c /home/tate/odoo/v19/v19.conf -d v19 --test-enable \
  --stop-after-init -i field_operation_contract
```

Sadece belirli bir test:

```bash
# ... yukarıdaki komuta ek olarak:
--test-tags=/odoo/tests/test_sale_order_contract_wizard.py
```

### Boşluklar (test planı için)

- **Section/note satırı senaryosu** — `date_start` required riski ([Bölüm 8 #1](#p0--olası-bug)).
- **`is_line_recurrence` auto-detection** — farklı periyotlarla line moduna geçiş.
- **Wizard warning mesajı** — `is_line_recurrence=True` iken `result['warning']`.
- **SO `state='sent'` zorlaması** — draft'tan veya cancel'dan gelen SO için.
- **Tax mapping boşluğu** — wizard ile oluşan sözleşmede vergi yok.
- **Multi-company** — farklı şirketlerde sözleşme izolasyonu.
- **ACL** — `service_group_user` dışı kullanıcı wizard çalıştıramaz.

---

## 10. Geliştirici Notları

### Sequence

- `data/ir_sequence_data.xml:4-10`: `FOC/` prefix, padding 5, company-independent.
- `create()` override (`models/field_operation_contract.py:454-459`) `name == "/"`
  ise `ir.sequence.next_by_code("field.operation.contract")` çağırır. Try/catch
  yok; sequence yoksa fallback `"New"`.

### Bulk create pattern (`_recurring_create_sale_ops`)

3 fazlı tasarım performans için:

1. **Hazırlık** — DB yazma olmadan tüm vals toplanır (`:190-213`)
2. **Toplu oluşturma** — Önce sale.order'lar bulk create, sonra field.operation'lar
   (`:218-233`)
3. **Takip** — generated_occurrences / recurring_next_date güncellemeleri ve log
   (`:235-249`)

Multi-company aware: contract'ları `company_id`'ye göre gruplar, her şirket için
`with_company` context'i ile işler (`:170-174`).

### Mixin (OCA Contract'tan ilham)

`models/service_contract_recurring_mixin.py` — abstract model, hem sözleşme
header'ında hem satırında inherit. Tarih hesaplama (`get_relative_delta`,
`get_next_period_date_end`, `get_next_recurring_date`) OCA Contract modülünün
mantığını takip eder.

### Migration notu

`migrations/19.0.1.0.1/post-migration.py:11-22` — `remaining_count > 1_000_000`
olan satırları düzeltir (eski mixin default değeri `10**9`'dan kaynaklı bug fix).

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
    └── test_sale_order_contract_wizard.py
```

---

## Lisans

AGPL-3 — `__manifest__.py:23`. Yazar: **Softteknik Bilişim** (`:21`),
[https://softteknik.com](https://softteknik.com).
