# Field Operation Pest Form

> Saha servis operasyonları için pest kontrol / biyosidal uygulama kayıtları.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.2.0`
> Modül: `apps/saha/field_operation_pest`

## 1. Genel Bakış

Bu modül **operation merkezlidir**: pest kontrol verisi `field.operation`
kaydına bağlıdır ve forms modülü olmadan da kullanılabilir. Operation üzerindeki
servis raporuna pest kontrol bölümü eklenir; imza, portal ve e-posta
`field_operation`'ın kendi altyapısını kullanır.

Form kullanan müşteriler için opsiyonel `field_operation_forms_pest` köprüsü
kurulur. Köprü, aynı satırları servis formuna bağlar; pest sekmesini, stok
teslimat akışını ve forms record rule'larını geri getirir.

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `field_operation` | `field.operation`, `field.operation.type`, servis PDF'i, portal ve imza |
| `product` | `product.product`, `product.template` ve ürün alanları |
| `stock` | **Yalnızca köprüde**; forms'suz kurulumda stok aktarımı yok |

## 3. Ana Modeller

| Model | Tür | İçerik |
|---|---|---|
| `field.operation.pesticide` | Yeni | `operation_id`, ürün, miktar, UoM, kullanılan ekipman |
| `field.operation.pest.type` | Yeni | Zararlı türü sözlüğü |
| `field.operation` | `_inherit` | Biyosidal başlıklar, `pest_type_ids`, `pesticide_ids` |
| `field.operation.type` | `_inherit` | `type` seçimine `pest` değeri |
| `product.template` | `_inherit` | `active_ingredient`, `package`, `antidote`, `vendor` |
| `res.company` | `_inherit` | `biocidal_certificate`, `responsible_manager` |

Pestisit satırı numarası `field.biocidal` serisinden gelir (`BIO-` öneki,
5 hane). Seri `data/ir_sequence_data.xml` içinde tanımlıdır.

## 4. Roller ve Güvenlik

Kendi grubunu tanımlamaz; `field_operation` gruplarını kullanır:

| ACL — Model | Grup | R/W/C/U |
|---|---|---|
| `field.operation.pesticide` | `service_group_worker` | 1/1/1/0 |
| `field.operation.pesticide` | `service_group_user` | 1/1/1/1 |
| `field.operation.pesticide` | `service_group_manager` | 1/1/1/1 |
| `field.operation.pest.type` | `service_group_worker` / `service_group_user` | 1/0/0/0 |
| `field.operation.pest.type` | `service_group_manager` | 1/1/1/1 |

Satır record rule'ları operation atamasına göredir (`team_leader_id`,
`person_ids.user_id`) ve global company kuralı vardır. Forms grupları için
ek kurallar köprü modülündedir.

## 5. PDF ve E-posta

- `field_operation` servis raporu (`field_work_delivery_pdf`), mevcut
  `o.tag_ids` bloğundan sonra inherit edilir; pest başlıkları, zararlı türleri
  ve pestisit satırları operation PDF'ine basılır.
- Rapor imza blokları operation'ın `form_signature` / `staff_signature`
  alanlarını kullanır.
- Müşteri e-postası `field_operation` şablonuyla, PDF ekli olarak gönderilir.
- `field_operation` çekirdeğine dokunulmaz.

## 6. Forms Köprüsü

`field_operation_forms_pest` kurulduğunda:
- Satıra `forms_id` eklenir; mevcut kolon ve veri korunur.
- Formdaki biyosidal başlıklar operation'daki değerlere related/writable bağlanır.
- Pest sekmesi, stok teslimat alanları/butonu ve forms record rule'ları geri gelir.
- Formdan satır oluşturulunca `operation_id`, formun operation'ından set edilir;
  formun operation'ı yoksa oluşturulur.

## 7. Veri Geçişi

`migrations/19.0.1.2.0/post-migrate.py` eski `forms_id` ilişkisinden
`operation_id`'yi doldurur. Forms'suz eski satırlar (53 kayıt) operation'sız
kalabilir; UI'da görünmezler. Form tarafındaki biyosidal başlıklar ve zararlı
türü bağlantıları köprü kurulumunda operation'a kopyalanır.

## 8. Testler

`tests/test_field_operation_pest.py` operation üzerinden satır oluşturma, seri
numarası, UoM ve başlık alanlarını doğrular. Forms/stok köprüsünün testleri
`field_operation_forms_pest/tests/` altındadır.
