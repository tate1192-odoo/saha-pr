# Field Operation Forms Disinfect

> `field_operation_disinfect` ile `field_operation_forms` arasındaki opsiyonel
> köprü: servis formu sekmesi, imzalı form PDF'i ve form e-postası.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.2.0`
> Modül: `apps/saha/field_operation_forms_disinfect`

## 1. Ne Yapar?

`field_operation_disinfect` operation merkezlidir; forms olmadan çalışır.
Forms kullanan müşterilerde bu köprü şunları geri getirir:

- `field.operation.forms` üzerindeki **Disinfect** sekmesi
- Formdaki PH/CL alanları (operation değerlerine related/writable)
- Formdan satır oluşturma ve `operation_id` eşlemesi
- İmzalı form PDF'i (`action_field_disinfect_pdf`)
- Form e-posta şablonu (`email_field_operation_form_biocidal`)
- Forms grupları için ACL ve record rule'lar

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `field_operation_disinfect` | Satır modeli, ürün kataloğu, operation alanları |
| `field_operation_forms` | `field.operation.forms`, forms grupları, PDF iskeleti |

## 3. Veri Modeli

- `field.operation.disinfect.forms_id` bu modülde eklenir. Kolon zaten mevcut
  olduğu için eski veri taşınmaz; yalnızca alan yeniden kaydedilir.
- `field.operation.forms.disinfect_ids` ve PH/CL alanları burada tanımlıdır.
- Formun operation'ı yoksa `_ensure_disinfect_operation()` oluşturur ve satırları
  bu operation'a bağlar.

## 4. Kurulum / Yükseltme

Uzman gibi forms kullanan bir veritabanında:

```bash
odoo-bin -c conf -d <db> \
  -u field_operation_disinfect \
  -i field_operation_forms_disinfect \
  --stop-after-init
```

`field_operation` çekirdeğine dokunulmaz. Disinfect, operation PDF'ine mevcut
`o.tag_ids` bloğundan sonra eklenir; forms köprüsü de eski form view'larını
kendi XMLID'leriyle günceller.

`pre_init_hook` eski `field_operation_disinfect` XMLID'lerini (form view, PDF,
rapor, e-posta, form alanları) köprüye taşır. Böylece kayıtlar kopyalanmaz,
yerinde güncellenir. `post_init_hook` eski form verisini operation'a bağlar ve
PH/CL değerlerini kopyalar.

Forms kullanmayan müşteride bu modül **kurulmaz**; `field_operation_disinfect`
tek başına operation PDF'i, portalı, imzası ve e-postasıyla çalışır.

## 5. Testler

`tests/test_field_operation_disinfect.py`:
- formdan satır oluşturma ve operation eşlemesi
- PH/CL alanlarının operation ile paylaşılması
- forms record rule'ları
- form e-posta aksiyonu
- forms'suz operation satırı
