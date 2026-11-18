# Field Operation Repeat

> Saha operasyonu paketinin tekrar (recurrence) katmanı: `service.repeat.wizard` sihirbazı,
> seri alanları ve yeniden planlama davranışı.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.0.0`
> Modül: `apps/saha/field_operation_repeat` · 18 dosya

Bu doküman modül kodundan üretilmiştir (manifest + models + wizard + views + tests).

## 1. Genel Bakış

Modül iki sorumluluğu sahiplenir:

1. **Tekrarlı operasyon sihirbazı** — `service.repeat.wizard` modeli, `service.repeat.wizard.form`
   view'ı ve `action_service_repeat_wizard` penceresi. 19.0.2.9.0'da `field_operation` bu sihirbazı
   bıraktı; tekrar üretimi artık buradan yapılır.
2. **Seri (series) katmanı** — bir servisi serinin kaynağı yapar, plan yeniden düzenlendiğinde
   seriyi hizada tutar.

Kapsam dışı: sözleşme bağlantısı (`field_operation_contract_repeat`), cron ile otomatik üretim,
fatura/portal akışı. Müşteriye özel etiket/alan içermez; o katman bu modüle bağımlı müşteri
modülünde kalır.

## 2. Sihirbaz (`service.repeat.wizard`)

- **Ayar alanları:** `partner_id`, `user_id`, `company_id`, `subject`, `service_type_id`,
  `dtstart`, `rrule_freq` / `rrule_interval`, haftalık `rrule_byweekday`, aylık
  `rrule_month_by` + `rrule_bymonthday` / `rrule_bysetpos` + `rrule_byweekday_pos`,
  bitiş için `rrule_end_type` + `rrule_count` / `rrule_until`.
- **Görünürlük:** `show_*` / `require_*` bayrakları `_compute_visibility_flags` ile hesaplanır
  (formda görünmez alanlar olarak taşınır).
- **Ayın günü:** `rrule_bymonthday` başlangıç tarihinden türetilir, elle değiştirilebilir
  (`_compute_rrule_bymonthday`) — "bugünün günü" hatasının regresyonu test edilir.
- **Üretim:** `action_generate_operations` → `rrule.rrule(**params)` üzerinden tarihler `islice`
  ile en fazla `max_recurring_operations` (varsayılan **500**, context ile değiştirilebilir)
  kadar üretilir; sınır tarihler üretilirken uygulanır, liste tamamen kurulmaz.
- **Kanca:** `_prepare_operation_values()` falsy dönerse o tarih **atlanır**. Kaynak servis ve
  sözleşme overlay'leri tarih filtrelemeyi bununla yapar.
- **Saat dilimi:** `_local_to_utc()` sırasıyla `context.tz` → kullanıcı `tz` → UTC.
- **Kayıtlar** `status = planned` ve referansı `/` (sequence atar) ile oluşur; üretim sonunda
  ilk kayda chatter notu düşülür.
- **Güvenlik:** `security/ir.model.access.csv` → `field_operation.service_group_user`
  (okuma/yazma/oluşturma/silme). Aksiyon `field_operation.group_field_operation_recurring`
  grubuna bağlıdır.

## 3. Kaynak servis overlay'i (`wizard/service_repeat_wizard_source.py`)

Sihirbazı mevcut bir servisten besler; kaynak opsiyoneldir, boşken çekirdek davranış aynıdır.

| alan | ne yapar |
|---|---|
| `field_operation_id` | kaynak servis; doluyken dialog kaynaktan dolar |
| `copy_from_source` | müşteri/adres/ekip/fiyat/etiket/açıklamayı kopyalar |
| `use_source_time` | saati ve süreyi kaynaktan alır (yerel saat → UTC) |
| `link_to_source` | üretilen periyotları `parent_id` ile seriye bağlar |
| `skip_existing` | kaynak seride o gün zaten periyot varsa atlar |
| `generated_status` | üretilen kayıtların durumu (`draft` / `planned`, varsayılan `planned`) |
| `preview_dates` | üretilecek tarihlerin önizlemesi (10 satır) |

`default_get` müşteri/konu/tip/kullanıcı/şirket ve yerel `dtstart`'ı doldurur; kaynak kendi
serisinin periyodu sayılmaz (kaynağın tarihi atlanır).

## 4. Seri (`models/field_operation.py`)

- `parent_id` / `child_ids`: kaynak servis ve ondan üretilen periyotlar.
- `write()` içinde `start_date` değişimi: seriye ait kayıtta sonraki periyotlar **tam gün**
  kadar kayar (`int(total_seconds()/86400)`; 2 saatlik geri kaydırma 0 gün sayılır).
- `done` / `cancel` periyotlar donar; donmuş (kapanmış) bir servis hareket ettirilirse gelecek
  periyotlar yerinde bırakılır ve uyarı üretilir.
- Seri hareketinde ekip/izin çakışma kontrolü bloklamaz: `SKIP_TEAM_CHECK_CONTEXT` ile atlanır,
  çakışmalar `_collect_shift_warnings` ile toplanıp bus toast + chatter notu olarak raporlanır.
  Seri dışı kayıtlarda çekirdeğin bloklayan kontrolü aynen çalışır (`_check_team_integrity`
  `@api.constrains` ile yeniden tanımlanır).
- Sadece `start_date` içeren yazımlar seriyi kaydırır; `end_date` değişikliği plan kaydırması
  sayılmaz (bilinçli).

## 5. View'lar

| view | ne yapar |
|---|---|
| `service.repeat.wizard.form` | sihirbaz formu (ayar grupları, koşullu alanlar, footer) |
| `field.operation.form.repeat` (inherit) | form başlığına **Repeat Service** butonu (`action_repeat_service`), notebook'a **Recurring Services** sayfası (`parent_id` + `child_ids` listesi) |
| `service.repeat.wizard.form.source` (inherit) | **Source Service** grubu, `generated_status`, **Preview** bloğu; kaynak doluyken müşteri/konu/tip/kullanıcı salt-okunur |

## 6. Testler

| dosya | test | kapsam |
|---|---|---|
| `tests/test_wizard_generation.py` | 3 | ayın günü başlangıçtan + elle değiştirilebilir, 500 sınırı tarihler üretilirken uygulanır |
| `tests/test_source_wizard.py` | 8 | `default_get`, kaynaktan üretim + chatter, gece servisi (00:30 yerel), `generated_status`, `skip_existing`, `link_to_source=False`, kaynaksız dialog, önizleme |
| `tests/test_series_shift.py` | 9 | ileri/geri tam gün kaydırma, geri 2 saatte kaydırmama, orta periyot, done periyot/kaynak, çakışmanın uyarıya dönüşmesi, seri dışı servisin bloklanmaya devam etmesi |

Doğrulama (temiz demo-less DB):

```shell
odoo-bin -c <conf> -d <db> -i field_operation_repeat --stop-after-init
odoo-bin -c <conf> -d <db> -u field_operation_repeat \
  --test-tags=/field_operation_repeat --stop-after-init
```

## 7. Dikkat edilecekler

- `depends`: `field_operation`, `bus`. `bus`, seri hareketinin çakışma uyarısını toast olarak
  göndermek için gerekir.
- Müşteri overlay'leri bu modüle bağımlı olmalı (`depends: field_operation_repeat`); çekirdek
  sihirbazı yeniden yazmak yerine `_prepare_operation_values` / `_inherit` kullanılmalı.
- `skip_existing` yalnızca kaynak serinin periyotlarına bakar (silinmiş/iptal periyotlar dahil).
- Sözleşme tarafı (`field_operation_contract_repeat`) bu modüldeki sihirbazı `contract_id`
  kaynağıyla genişletir; ayrı bir sihirbaz modeli yoktur.
