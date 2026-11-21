# Field Operation Forms Disinfect

> `field_operation_disinfect` ile `field_operation_forms` arasındaki opsiyonel
> köprü: servis formu sekmesi, bağımsız form satırları, imzalı form PDF'i ve
> form e-postası.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.3.0`
> Modül: `apps/saha/field_operation_forms_disinfect`

## 1. Ne Yapar?

`field_operation_disinfect` operation merkezlidir; forms olmadan çalışır.
Forms kullanan müşterilerde bu köprü şunları getirir:

- `field.operation.forms` üzerindeki **Disinfect** sekmesi
- Form üzerinde tutulan PH/CL alanları
- Form satırları için bağımsız model: `field.operation.forms.disinfect`
- İmzalı form PDF'i (`action_field_disinfect_pdf`)
- Form e-posta şablonu (`email_field_operation_form_biocidal`)
- Forms grupları için ACL ve record rule'lar

Form akışı **operation oluşturmaz veya operation verisini değiştirmez**.
Müşteri kaydı form üzerinden takip eder.

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `field_operation_disinfect` | Ürün kataloğu (`field.disinfect.product`) ve ortak dezenfeksiyon verisi |
| `field_operation_forms` | `field.operation.forms`, forms grupları, PDF iskeleti |

Operation tarafındaki `field.operation.disinfect` modeli bu modülden bağımsız
kalır; forms köprüsü onu genişletmez.

## 3. Veri Modeli

- `field.operation.forms.disinfect` bu modülde tanımlıdır:
  - `forms_id` (`ondelete="cascade"`): form silinince satırlar da silinir.
  - `name` (`field.forms.disinfect` sequence, `DIS-F-` + 5 hane)
  - `sequence`, `product_id`, `tank_dimensions`, `cleaning`, `disinfection`,
    `ozone`, `filter_change`.
- `field.operation.forms.disinfect_ids` bu modeli gösterir.
- `before_ph`, `after_ph`, `before_cl`, `after_cl` alanları form üzerinde
  saklanır; operation'a related değildir.
- Formun `operation_id` alanı doldurulmaz; `_ensure_disinfect_operation()`
  kaldırılmıştır.

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
yerinde güncellenir.

`19.0.1.3.0` yükseltmesinde `post-migrate.py`:

- eski `field_operation_disinfect.forms_id` dolu satırları yeni
  `field_operation_forms_disinfect` tablosuna kopyalar (eski `name` referansı
  varsa korunur; yoksa yeni `DIS-F-` sequence'i atanır);
- operasyondaki PH/CL değerlerini form alanlarına taşır.

`auto_install` açıktır: `field_operation_forms` + `field_operation_disinfect`
kurulu olan yeni bir veritabanında köprü kendiliğinden kurulur. Mevcut bir
çiftte (Uzman gibi) elle `-i field_operation_forms_disinfect` gerekir.

Forms kullanmayan müşteride bu modül **kurulmaz**; `field_operation_disinfect`
tek başına operation PDF'i, portalı, imzası ve e-postasıyla çalışır.

## 5. Testler

`tests/test_field_operation_disinfect.py`:
- form satırının yalnız forma bağlı olması, operation oluşturmaması
- PH/CL alanlarının formda saklanması
- forms record rule'ları
- form e-posta aksiyonu
- form silinince satırların cascade silinmesi
