# Field Operation Contract Repeat Wizard

> Sözleşmeden (field.operation.contract) elle, talep üzerine toplu tekrarlayan saha işi
> (field.operation) üretimi — tekrar motoru `field_operation_repeat` ile paylaşılır.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.2.0.0`

Bu doküman modül kodundan üretilmiştir (manifest + wizard overlay + view XML + testler).

## 1. Genel Bakış

`field_operation_contract` modülünden ayrılmış, bağımsız lisanslanabilen opsiyonel eklenti.
Sözleşme formuna **Repeat Contract Service** butonu ekler; buton
`field_operation_repeat.action_service_repeat_wizard` aksiyonunu `default_contract_id`
context'iyle açar, yani aynı sihirbaz sözleşme kaynağıyla çalışır.

Modülün **kendi modeli yoktur**: `service.repeat.wizard` modelini `_inherit` ile genişletir.
`rrule` motoru, saat dilimi çevrimi, `max_recurring_operations` sınırı, tarih önizlemesi ve
kaynak servis desteği `field_operation_repeat` tarafındadır; burada yalnız sözleşmeye özgü
katman durur.

## 2. Eklediği alanlar

| alan | tür | ne yapar |
|---|---|---|
| `contract_id` | m2o `field.operation.contract` | kaynak sözleşme; doluyken müşteri/konu/tip/kullanıcı salt-okunur, planlama sözleşmeden gelir |
| `skipped_count` | integer (readonly) | son çalıştırmada zaten planlı olduğu için atlanan tarih sayısı (test ve chatter için; dialog üretimden sonra kapandığı için view'da gösterilmez, sonuç bildirim + chatter'da) |

## 3. Davranış

- **Doldurma:** `create()` (RPC/test), `default_get` (form context'i) ve `onchange` (sihirbaz
  içinde elle sözleşme seçimi) aynı `_contract_defaults()` sözlüğünü kullanır: müşteri,
  sorumlu, şirket, konu, ilk hizmet tipi, `dtstart = contract.date_start`, `skip_existing=True`,
  `generated_status="draft"`; `date_end` doluysa `rrule_end_type="until"` + `rrule_until`.
- **Mükerrer koruması:** `skip_existing` açıkken sözleşmenin o gün için operasyonu varsa tarih
  atlanır, `skipped_count` artar.
- **Üretilen kayıt:** gün boyu sürer (`end_date = start + 1 gün`, Gantt start–end arasını çizer),
  `contract_id` ve `generated_status` yazılır.
- **Raporlama:** her çalıştırma sözleşmeye chatter notu düşer; hiç kayıt üretilmediyse veya
  atlanan varsa `display_notification` ile bildirilir, üretilen varsa oluşan kayıtların listesi
  açılır.

Devraldıkları (tekrar yazılmaz): sıklık/aralık/bitiş kuralları, `until` kapsayıcılığı, aylık
"gün / haftanın günü" seçenekleri, `context.tz → kullanıcı tz → UTC` çevrimi, 500 kayıt güvenlik
sınırı (üretim sırasında uygulanır), tarih önizlemesi, kaynak servis sihirbazı.

## 4. Kurulum / bağımlılık

```json
"depends": ["field_operation_contract", "field_operation_repeat"]
```

19.0.2.0.0 öncesinde modül kendi `service.contract.repeat.wizard` modelini ve ACL dosyasını
taşıyordu; o model kaldırıldı. Yetki artık `service.repeat.wizard` üzerinden
`field_operation_repeat`'ten gelir (`security/ir.model.access.csv` yok).

## 5. Testler

`tests/test_service_repeat_wizard.py` — 13 test: sözleşmeden doldurma (`create`, `default_get`,
`onchange`), aylık günün başlangıç tarihini izlemesi, üretilen kayıtların içeriği, saat dilimi
çevrimi, her sıklık/bitiş tipi için `rrule` parametreleri, `until` kapsayıcılığı, 500 sınırı,
geçersiz ayarların reddi, zaten planlı tarihlerin atlanması, başka sözleşmenin benzer tarihinin
mükerrer sayılmaması, butonun grup + sözleşme context'i.

**Doğrulama:** temiz demo-less DB'de `-i field_operation_contract_repeat` ardından
`-u field_operation_contract_repeat --test-tags=/field_operation_contract_repeat`.
