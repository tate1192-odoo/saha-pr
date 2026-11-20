# Field Operation Disinfect

> Dezenfeksiyon / biyosidal uygulama kayıtları — tank ve dispenser satırları,
> PH/CL ölçümleri, operation PDF'i ve e-posta şablonu.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.2.0`
> Modül: `apps/saha/field_operation_disinfect`

## 1. Genel Bakış

Bu modül **operation merkezlidir**: dezenfeksiyon verisi `field.operation`
kaydına bağlıdır ve forms modülü olmadan da kullanılabilir. `field.operation`
üzerindeki servis raporuna dezenfeksiyon bölümü eklenir; imza, portal ve
e-posta `field_operation`'ın kendi altyapısını kullanır.

Form kullanan müşteriler için opsiyonel `field_operation_forms_disinfect`
köprüsü kurulur. Köprü, aynı satırları servis formuna bağlar ve form PDF'i ile
form e-postasını geri getirir.

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `field_operation` | `field.operation`, `field.operation.type`, servis PDF'i, portal ve imza |

`field_operation_forms` bu modülün bağımlılığı **değildir**. Forms kullanan
müşteride `field_operation_forms_disinfect` köprüsü ayrıca kurulur.

## 3. Ana Modeller

| Model | Tür | İçerik |
|---|---|---|
| `field.operation.disinfect` | Yeni | `operation_id`, `product_id`, temizlik/dezenfeksiyon/ozon/filtre bayrakları, tank ölçüsü, tarihler |
| `field.disinfect.product` | Yeni | Ürün/stok kataloğu (Dispenser / Tank) |
| `field.operation` | `_inherit` | `before_ph`, `after_ph`, `before_cl`, `after_cl`, `disinfect_ids` |
| `field.operation.type` | `_inherit` | `type` seçimine `disinfect` değeri |
| `res.company` | `_inherit` | `disinfection_certificate` |

Numara üretimi: `field.operation.disinfect.create()` içinde `ir.sequence` kodu
`field.disinfect` çağrılır. Seri `data/ir_sequence_data.xml` içinde tanımlıdır
(`DIS-` öneki, 5 hane).

## 4. Roller ve Güvenlik

Kendi grubunu tanımlamaz; `field_operation` gruplarını kullanır:

| ACL — Model | Grup | R/W/C/U |
|---|---|---|
| `field.operation.disinfect` | `service_group_worker` | 1/1/1/0 |
| `field.operation.disinfect` | `service_group_user` | 1/1/1/1 |
| `field.operation.disinfect` | `service_group_manager` | 1/1/1/1 |
| `field.disinfect.product` | `service_group_worker` / `service_group_user` | 1/0/0/0 |
| `field.disinfect.product` | `service_group_manager` | 1/1/1/1 |

Record rule'ları operation atamasına göredir (`team_leader_id`,
`person_ids.user_id`) ve global company kuralı vardır. Forms grupları için
ek kurallar köprü modülündedir.

## 5. PDF ve E-posta

- Bu modül, `field_operation` servis raporunu (`field_work_delivery_pdf`)
  mevcut `o.tag_ids` bloğundan sonra inherit eder; dezenfeksiyon satırlarını ve
  PH/CL değerlerini oraya basar. `field_operation` çekirdeğine dokunulmaz.
- Rapor imza blokları operation'ın `form_signature` / `staff_signature`
  alanlarını kullanır.
- Müşteri e-postası `field_operation` şablonuyla, PDF ekli olarak gönderilir.

## 6. Forms Köprüsü

`field_operation_forms_disinfect` kurulduğunda:
- Satıra `forms_id` eklenir; mevcut kolon ve veri korunur.
- Formdaki `before_ph` / `after_ph` / `before_cl` / `after_cl` alanları
  operation'daki değerlere related/writable bağlanır.
- Servis formu sekmesi, form PDF'i ve form e-posta şablonu geri gelir.
- Formdan satır oluşturulunca `operation_id`, formun operation'ından set edilir;
  formun operation'ı yoksa oluşturulur.

## 7. Veri Geçişi

`migrations/19.0.1.2.0/post-migrate.py` eski `forms_id` ilişkisinden
`operation_id`'yi doldurur. Operation'ı olmayan eski satırlar (23 kayıt) null
kalabilir; yeni kayıtlar operation zorunlu olacak şekilde view'da işaretlidir.
Form tarafındaki eski PH/CL kolonları köprü kurulumunda operation'a kopyalanır.

## 8. Testler

`tests/test_field_operation_disinfect.py` operation üzerinden satır oluşturma,
seri numarası ve PH/CL alanlarını doğrular. Forms köprüsünün testleri
`field_operation_forms_disinfect/tests/` altındadır.
