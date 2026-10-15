# Field Operation Contract Repeat Wizard

> Sözleşmeden (field.operation.contract) elle, talep üzerine toplu tekrarlayan saha işi
> (field.operation) üreten sihirbaz — iCalendar rrule kuralları ile.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.0.0`
> Modül: `apps/saha/field_operation_contract_repeat` · 11 dosya · 1 yeni TransientModel içerir

Bu doküman modül kodundan üretilmiştir (manifest + wizard Python + view XML + ACL + testler). Kodda
kanıtı olmayan iş bilgisi `<!-- DOLDURULACAK -->` ile işaretlenmiştir.

## 1. Genel Bakış

`field_operation_contract` modülünden ayrılmış, bağımsız lisanslanabilen opsiyonel eklenti.
Sözleşme formuna **Repeat Contract Service** butonu ekler; buton
`service.contract.repeat.wizard` sihirbazını açar ve seçilen kurala göre `field.operation`
kayıtlarını toplu oluşturur.

- Sıklıklar: günlük, haftalık, aylık, yıllık; haftalık/aylık için ek seçenekler
- Bitiş koşulu: belirli adet (`count`) veya belirli tarih (`until`, **kapsayıcı** — bitiş günü dahil)
- Güvenlik sınırı: tek çalıştırmada `max_recurring_operations` (varsayılan **500**); sınır tarihler
  üretilirken uygulanır, liste tamamen kurulmaz
- Üretilen kayıtlar `status = draft` yazılır (sözleşme cron üreticisiyle aynı akış)
- **Mükerrer koruması:** aynı sözleşmede aynı tarihte iş varsa o tarih atlanır ve kaç kaydın
  atlandığı bildirilir
- **Saat dilimi:** `context.tz` → kullanıcı tz → UTC sırasıyla çevrilir; işler yerel 00:00'a denk gelir

Kapsam dışı: cron kurmaz, mevcut kayıtları güncellemez, `ir.rule` tanımlamaz (kendi modeli
transient'tir; üretilen kayıtların güvenliği `field.operation` tarafından yönetilir).

<!-- DOLDURULACAK: Cron tabanlı otomatik tekrar yerine bu elle sihirbaz hangi iş senaryosunda tercih ediliyor? -->

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `field_operation_contract` | `field.operation.contract` modeli (`partner_id`, `service_type_ids`, `user_id`, `company_id`, `subject`, `date_start`, `date_end`) ve inherit edilen `view_field_operation_contract_form` |
| `field_operation` (dolaylı) | `field.operation` modeli, `field_operation.action_field_operation` aksiyonu, buton ve ACL'deki `group_field_operation_recurring` grubu |

## 3. Ana Modeller

| Model | Tür | Rol |
|---|---|---|
| `service.contract.repeat.wizard` | **Yeni** (`TransientModel`) | Tekrar parametrelerini toplar, `action_generate_operations` ile kayıt üretir |
| `field.operation` | Kullanılan | Üretilen saha işleri (`create`) |
| `field.operation.contract` | Kullanılan | Kaynak sözleşme; formunda buton inherit edilir |
| `field.operation.type` | Kullanılan | `service_type_id` seçimi (boşsa sözleşmenin ilk servis tipi) |
| `res.partner` / `res.users` / `res.company` | Kullanılan | Müşteri, sorumlu, şirket |

Sihirbaz alanları: `contract_id`, `partner_id`, `user_id`, `company_id`, `subject`,
`service_type_id`, `start_date`, `end_date`, `rrule_freq`, `rrule_interval`, `rrule_byweekday`,
`rrule_month_by`, `rrule_bymonthday`, `rrule_bysetpos`, `rrule_byweekday_pos`, `rrule_end_type`,
`rrule_count` + 10 hesaplanan görünürlük/zorunluluk bayrağı (`show_*`, `require_*`).

**Sözleşmeden türeyen alanlar `compute` ile doldurulur** (`store=True, readonly=False,
precompute=True`), `onchange` ile değil: `onchange` yalnız formda çalışır, ORM/RPC ile `create`
çağrısında çalışmaz ve zorunlu alanlar boş kalıp NOT NULL ihlali veriyordu. Kullanıcı değerlerin
üzerine yazabilir. `rrule_bymonthday` **başlangıç tarihinden** türer (eskiden bugünün günüydü:
1 Kasım'da başlayan aylık kural işleri ayın 11'inde üretiyordu) ve elle değiştirilebilir.

## 4. Roller ve Güvenlik

- **Buton:** `groups="field_operation.group_field_operation_recurring"` — suite'in kendi tekrar
  sihirbazının kullandığı grupla aynı (`field_operation/views/field_operation_view.xml`). İptal
  edilmiş sözleşmede gizlidir (`invisible="state == 'cancel'"`) ve
  `context="{'default_contract_id': id}"` ile açık sözleşmeyi sihirbaza taşır.
- **ACL (tek satır):** `model_service_contract_repeat_wizard` → `field_operation.group_field_operation_recurring`,
  izinler `1,1,1,1`. `ir.rule` yok; model `TransientModel` olduğu için kalıcı kayıt bırakmaz.
- **View düzeyi:** `user_id` → `groups="base.group_user"`, `company_id` → `groups="base.group_multi_company"`.
- **Yetki yükseltme yok:** üretim `FieldOperation.create(...)` ile yapılır, `sudo()` kullanılmaz —
  çağıran kullanıcının `field.operation` yazma yetkisi gerekir.
- **Üretilen kayıtların güvenliği:** `field.operation` ACL/rule setine tabidir, bu modül kısıt eklemez.

## 5. Ana Akış

Menü kaydı yoktur; giriş noktası sözleşme formundaki başlık butonudur.

| Adım | Kayıt / Metod | Detay |
|---|---|---|
| Buton | `field_operation_contract_view_form_inherit_repeat` | `field.operation.contract` formunda `//button[@name='action_cancel']` **sonrasına** eklenir; "Repeat Contract Service", `type="action"`, `icon="fa-repeat"`, `groups` + `context` yukarıdaki gibi |
| Aksiyon | `action_service_contract_repeat_wizard` | `res_model=service.contract.repeat.wizard`, `view_mode=form`, `target=new` |
| Form | `service_contract_repeat_wizard_view_form` | Başlık "Generate Recurring Operations" |
| Varsayılanlar | `_compute_contract_defaults` | Sözleşmeden `partner_id`, `user_id`, `company_id`, `subject`, `service_type_id`, `start_date`, `end_date` |
| Çalıştırma | `action_generate_operations` | `rrule.rrule(**params)` + `islice` ile sınırlı üretim; mükerrer tarihler atlanır; toplu `create`; sözleşmeye chatter notu (`_log_generation`) |

| Dönüş durumu | Sonuç |
|---|---|
| Kayıt üretildi, mükerrer yok | `field_operation.action_field_operation`, `domain=[('id','in',created_ids)]`, ad "Generated Operations (N)" |
| Kayıt üretildi **ve** mükerrer atlandı | `display_notification` (uyarı: "N üretildi, M atlandı") + `params.next` ile yine aynı liste aksiyonu |
| Hiç yeni kayıt yok (hepsi mükerrer) | `display_notification` (uyarı), "No Operations Generated" |
| Sınır aşıldı / kural hatalı | `UserError` / `ValidationError` doğrudan yükseltilir; beklenmeyen hata `UserError`'a sarılır (`from error` ile kök korunur) |

Doğrulamalar (`@api.constrains`): `rrule_interval > 0`; aylık + `month_by='date'` iken
`rrule_bymonthday` 1–31; `end_type='count'` iken `rrule_count > 0`; `end_type='until'` iken
`end_date` zorunlu ve `start_date`'ten önce olamaz.

## 6. Alan Eşlemeleri / Liste Kolonları

`_prepare_operation_values()` her üretilen tarih için şu `field.operation` değerlerini yazar:

| Sihirbaz alanı | `field.operation` | Not |
|---|---|---|
| — (sabit) | `name` | `'/'` yazılır; numarayı `field.operation` atar (`FO/00442` gibi) |
| `subject` | `subject` | |
| `partner_id` / `company_id` / `user_id` | aynı adlar | |
| `service_type_id` | `service_type_id` | Boşsa sözleşmenin ilk servis tipi (`contract.service_type_ids[:1]`) |
| `contract_id` | `contract_id` | Tekrar ilişkisi burada kurulur |
| — (rrule tarihi, yerel 00:00) | `start_date` | `_local_to_utc` ile UTC'ye çevrilir |
| — (rrule tarihi + 1 gün) | `end_date` | Gantt görünümü çubukları `start_date`/`end_date` arasına çizer; `end_date` boşsa çubuk sıfır uzunlukta olur |
| — (sabit) | `status` | `'draft'` — sözleşme cron üreticisiyle aynı başlangıç durumu |

Sihirbazda liste/kanban görünümü yoktur (yalnız `form` + `target=new`).

## 7. Arama Filtreleri

Bu modül arama görünümü tanımlamaz. Sözleşme formuna yalnız bir buton inherit edilir;
`field.operation.contract` arama görünümü `field_operation_contract` modülünden gelir ve
bu modül tarafından değiştirilmez.

## 8. Test Kapsamı

`tests/test_service_contract_repeat_wizard.py` — **14 test** (`post_install`):

| Test | Neyi sabitler |
|---|---|
| `test_creating_with_the_contract_only_fills_the_required_fields` | Yalnız `contract_id` ile `create` çalışır (compute + `precompute`; NOT NULL ihlali yok) |
| `test_the_monthly_day_follows_the_start_date` | Aylık kural başlangıç gününde tekrarlar (11'i değil, 1'i) |
| `test_the_generated_operations_content` | `status='draft'`, `end_date = start + 1 gün`, numara atanmış, tip sözleşmeden |
| `test_the_start_date_is_converted_from_the_user_timezone` | `tz=Europe/Istanbul` + `2026-11-01` → kayıt `2026-10-31 21:00:00` |
| `test_rrule_params_for_every_frequency_and_end_type` | `dtstart` / `until` / `byweekday` / `bymonthday` / `freq` anahtarları |
| `test_every_weekday_selection_value_maps_to_a_recurrence_day` | Seçim listesi ile rrule haritası ayrışmaz |
| `test_an_until_recurrence_includes_the_end_date` | `until` kapsayıcı (5 gün → 5 kayıt) |
| `test_the_cap_is_enforced_before_every_date_is_produced` | `count=10.000.000` → `UserError`, 5 sn altı, kayıt üretilmemiş |
| `test_constraints_refuse_invalid_settings` | `interval=0`, `count=0`, `until<start`, `bymonthday=45` |
| `test_the_dates_already_planned_are_skipped` | İkinci çalıştırma mükerrer üretmez, uyarı döner |
| `test_new_dates_are_still_created_next_to_the_skipped_ones` | Kısmi mükerrerde yeni tarihler üretilir, uyarı `next` ile listeyi açar |
| `test_a_similar_date_of_another_contract_is_not_a_duplicate` | Mükerrer kontrolü sözleşme kapsamındadır |
| `test_the_wizard_is_reserved_to_the_recurring_planning_group` | ACL satırı `group_field_operation_recurring` |
| `test_the_button_carries_the_group_and_the_current_contract` | Butonda `groups` + `default_contract_id` var |

## 9. Geliştirici Notları

- `migrations/` yok; şema değişikliği üretmeyen sihirbaz modülü. `i18n/field_operation_contract_repeat.pot`
  + `i18n/tr.po` (çeviri iskeleti) ve `static/description/index.html` mevcut.
- **Sınır** (`max_recurring_operations`) tarihler `islice` ile üretilirken uygulanır: `rrule_count`
  sınırsız bir `Integer` olduğu için önce listeyi tamamen kurup sonra kontrol etmek, 100.000 tarihi
  0,14 saniyede üretip ardından hata vermek demekti.
- **Saat dilimi** dönüşümü `_local_to_utc` ile yapılır (`context.tz` → kullanıcı tz → UTC). Kardeş
  sihirbaz `field_operation/wizard/service_repeat_wizard.py` aynı yardımcıyı taşır; rrule üretim
  mantığı iki dosyada kopyadır ve ortak bir mixin'e çıkarılabilir.
- Aynı iki kusur (aylık gün varsayılanı ve sınır sırası) kardeş modülde de düzeltildi ve orada
  `field_operation/tests/test_service_repeat_wizard.py` ile sabitlendi.
- `dateutil.rrule` Odoo'nun çekirdek gereksinimleri arasındadır; `external_dependencies` gerekmez.
