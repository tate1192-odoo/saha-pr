# Field Operation Forms Pest

> `field_operation_pest` ile `field_operation_forms` arasındaki opsiyonel köprü:
> pest sekmesi, bağımsız pest satırları, stok teslimat akışı ve forms record
> rule'ları.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.3.0`
> Modül: `apps/saha/field_operation_forms_pest`

## 1. Ne Yapar?

`field_operation_pest` operation merkezlidir; forms olmadan çalışır.
Forms kullanan müşterilerde bu köprü şunları getirir:

- `field.operation.forms` üzerindeki **Pesticide** sekmesi ve biyosidal grup
- Form üzerinde tutulan biyosidal başlıklar
- Bağımsız form satır modeli: `field.operation.forms.pest`
- Zararlı türü seçimi
- Stok teslimat alanları, `action_transfer` ve teslimat smart button'ı
- Forms grupları için ACL ve record rule'lar
- `stock.move` / `stock.picking` üzerindeki `field_operation_form_id` alanları

Form akışı **operation oluşturmaz veya operation verisini değiştirmez**.
Müşteri kaydı form üzerinden takip eder.

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `field_operation_pest` | Pest türü ve operation tarafındaki pest verisi |
| `field_operation_forms` | `field.operation.forms`, forms grupları |
| `stock` | Teslimat emri ve stok hareketleri |

## 3. Veri Modeli

- `field.operation.forms.pest` bu modülde tanımlıdır:
  - `forms_id` (`ondelete="cascade"`): form silinince satırlar da silinir.
  - `name` (`field.forms.pest` sequence, `BIO-F-` + 5 hane)
  - `sequence`, `product_id`, `product_uom`, `product_qty`, `used_equipment`.
- `field.operation.forms.pesticide_ids` bu modeli gösterir.
- `hygiene`, `infestation`, `insulation`, `storage`, `efk_ift`, `monitors`,
  `others`, `residence`, `place`, `application_method`,
  `security_precautions`, `responsible_manager_id`, `application_place`,
  `pest_type_ids` form üzerinde saklanır; operation'a related değildir.
- Formun `operation_id` alanı doldurulmaz; `_ensure_pest_operation()`
  kaldırılmıştır.
- `action_transfer`, formdaki pestisit satırlarından `stock.picking` üretir;
  picking `field_operation_form_id` ile forma bağlanır.

## 4. Kurulum / Yükseltme

Uzman gibi forms kullanan bir veritabanında:

```bash
odoo-bin -c conf -d <db> \
  -u field_operation_pest \
  -i field_operation_forms_pest \
  --stop-after-init
```

`pre_init_hook` eski `field_operation_pest` XMLID'lerini (form view'ları, form
alanları, stok alanları, seçim değerleri) köprüye taşır.

`post_init_hook` ve `migrations/19.0.1.3.0/post-migrate.py` ortak
`migration_utils.copy_legacy_form_data()` fonksiyonunu çağırır:

- eski `field_operation_pesticide.forms_id` dolu satırları yeni
  `field_operation_forms_pest` tablosuna kopyalar (eski `BIO-` referansı
  varsa korunur; yoksa `BIO-F-` sequence'i atanır);
- biyosidal başlıkları operation'dan forma kopyalar;
- `pest_type_ids` ilişkisini operation'dan forma kopyalar;
- stok kolonları düşmüşse `stock_picking.field_operation_form_id` üzerinden
  picking tipi ve lokasyonları geri kurar.

`auto_install` açıktır: `field_operation_forms` + `field_operation_pest` + `stock`
kurulu olan yeni bir veritabanında köprü kendiliğinden kurulur. Mevcut bir
çiftte (Uzman gibi) elle `-i field_operation_forms_pest` gerekir.

Forms kullanmayan müşteride bu modül **kurulmaz**; `field_operation_pest` tek
başına operation PDF'i, portalı, imzası ve e-postasıyla çalışır. Stok teslimat
akışı yalnızca köprüde tanımlıdır.

## 5. Testler

`tests/test_field_operation_pest.py`:
- form satırının yalnız forma bağlı olması, operation oluşturmaması
- satır referansının `BIO-F-` sequence'inden gelmesi
- teslimat guard'ları ve picking bağlantısı
- form/operation görünüm kapıları
- forms'suz operation satırı
- biyosidal başlıkların ve pest türlerinin formda saklanması
- form silinince satırların cascade silinmesi
