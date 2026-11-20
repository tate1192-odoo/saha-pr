# Field Operation Forms Pest

> `field_operation_pest` ile `field_operation_forms` arasındaki opsiyonel köprü:
> pest sekmesi, stok teslimat akışı ve forms record rule'ları.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.2.0`
> Modül: `apps/saha/field_operation_forms_pest`

## 1. Ne Yapar?

`field_operation_pest` operation merkezlidir; forms olmadan çalışır.
Forms kullanan müşterilerde bu köprü şunları geri getirir:

- `field.operation.forms` üzerindeki **Pesticide** sekmesi ve biyosidal grup
- Formdaki biyosidal başlıkların operation değerlerine related/writable bağlanması
- Zararlı türü seçimi
- Stok teslimat alanları, `action_transfer` ve teslimat smart button'ı
- Forms grupları için ACL ve record rule'lar
- `stock.move` / `stock.picking` üzerindeki `field_operation_form_id` alanları

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `field_operation_pest` | Pestisit satırı, pest türü, operation alanları |
| `field_operation_forms` | `field.operation.forms`, forms grupları |
| `stock` | Teslimat emri ve stok hareketleri |

## 3. Veri Modeli

- `field.operation.pesticide.forms_id` bu modülde eklenir. Kolon zaten mevcut
  olduğu için eski veri taşınmaz; yalnızca alan yeniden kaydedilir.
- `forms_id` `ondelete="set null"`: form silinirse satır operation'da kalır.
- Formun biyosidal başlıkları `operation_id` üzerinden okunur/yazılır.
- Formun operation'ı yoksa `_ensure_pest_operation()` oluşturur ve satırları
  bu operation'a bağlar.
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
alanları, stok alanları, seçim değerleri) köprüye taşır. `post_init_hook`
operation'ı olmayan formları bağlar, satırları operation'a taşır, biyosidal
başlıkları ve zararlı türlerini operation'a kopyalar.

`auto_install` açıktır: `field_operation_forms` + `field_operation_pest` + `stock`
kurulu olan yeni bir veritabanında köprü kendiliğinden kurulur. Mevcut bir
çiftte (Uzman gibi) elle `-i field_operation_forms_pest` gerekir.

Forms kullanmayan müşteride bu modül **kurulmaz**; `field_operation_pest` tek
başına operation PDF'i, portalı, imzası ve e-postasıyla çalışır. Stok teslimat
akışı yalnızca köprüde tanımlıdır.

## 5. Testler

`tests/test_field_operation_pest.py`:
- formdan pestisit satırı oluşturma ve operation eşlemesi
- teslimat guard'ları ve picking bağlantısı
- form/operation görünüm kapıları
- forms'suz operation satırı
- biyosidal başlıkların operation ile paylaşılması
