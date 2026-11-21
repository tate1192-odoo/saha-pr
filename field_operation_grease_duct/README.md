# Field Operation Grease Duct

> Saha operasyonları için yağlı kanal (davlumbaz / yatay-dikey kanal / filtre) temizlik
> ölçümleri ve müşteriye verilen **temizlik sertifikası** çıktısı.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.1.0`
> Modül: `apps/saha/field_operation_grease_duct` · 1 yeni model içerir

## 1. Genel Bakış

`field.operation` (saha operasyonu) kaydına yağlı kanal temizliği boyutunu ekler: operasyon
başına ölçüm satırları, erişim durumu/notu, sertifika numarası, sonraki temizlik tarihi ve
bu değerleri **sertifika olarak basan** QWeb PDF raporu.

- `field.operation.grease.duct` — operasyon satırı: `operation_id`, tip (davlumbaz /
  dikey kanal / yatay kanal / filtre / diğer), adet, metre, not
- `field.operation` üzerine: `grease_duct_ids`, `grease_duct_no`, `grease_access_status`,
  `grease_access_note`, `grease_next_cleaning_date`, `grease_total_length` (hesaplanan)
- `field.operation.type` seçimine `grease_duct` değeri; form alanları yalnız bu tip seçilince görünür
- Sertifika PDF'i (`Grease Duct Certificate`) operasyon üzerinden yazdırılır

Operasyon merkezli bu modül `field_operation_forms` gerektirmez. Servis formu kullanan
müşteriler için opsiyonel `field_operation_forms_grease_duct` modülü ayrıca kurulabilir.

Kapsam dışı: otomatik yenileme/cron kurmaz, portal denetleyicisi tanımlamaz, e-posta şablonu
göndermez, ürün/stok entegrasyonu içermez.

## 2. Bağımlılıklar

| Modül | Neden |
|---|---|
| `field_operation` | `field.operation`, `field.operation.type` ve `service_group_*` grupları |

## 3. Modeller

| Model | Tür | İçerik |
|---|---|---|
| `field.operation.grease.duct` | **Yeni**, `_order = "sequence, id"` | `operation_id` (cascade), `company_id` (related), `duct_type`, `quantity` (AD), `length` (MT), `note` |
| `field.operation` | Genişletme | `grease_duct_ids`, `grease_duct_no` (sequence, readonly), `grease_access_status`, `grease_access_note`, `grease_next_cleaning_date`, `grease_total_length` (compute) |
| `field.operation.type` | Genişletme | `type` seçimine `grease_duct` |

### Sertifika numarası

`ir.sequence` kodu `field.grease`, prefix `GRD-<yıl>-`, 4 hane. Numara yalnız servis tipi
`grease_duct` olan operasyonlara atanır: `create` sırasında tip yağlı kanalsa, sonradan tip
değiştirildiğinde `write` içinde atanır. Başka servis tiplerinde alan boş kalır.

### Toplam uzunluk

`grease_total_length`, `grease_duct_ids.length` alanlarının toplamıdır (compute, saklanmaz).
Sertifikada "Toplam Kanal Uzunluğu" satırında basılır.

## 4. Güvenlik

- `security/ir.model.access.csv`: `service_group_worker` (okuma/yazma/oluşturma),
  `service_group_user` ve `service_group_manager` (tam yetki)
- `security/grease_duct_security.xml`: kullanıcı yalnız kendi ekibinin/atanmış olduğu
  operasyonların satırlarını görür, ofis kullanıcıları ve yönetici tümünü görür, satırlar
  `company_id` ile şirkete izole edilir

## 5. Sertifika Çıktısı

`field.operation` üzerinden **Print → Grease Duct Certificate**. Basılan değerler:

1. Sertifika no + tarih (`start_date`)
2. Müşteri, adres, telefon/e-posta
3. Teknisyenler (operasyonun `person_ids` alanı)
4. Ölçüm tablosu: tip / adet / metre / not + toplam metre
5. Kanal erişimi (Tam / Kısmi / Erişim yok) ve erişim notu (ör. "kedi yolu yapılmalı")
6. Yapılan işlem (operasyonun `solution` alanı)
7. Sonraki temizlik tarihi
8. Personel ve müşteri imzaları (operasyonun imza alanları)

Şablonlar: `report/grease_duct_templates.xml`, rapor aksiyonu: `report/grease_duct_reports.xml`.

## 6. Testler

`tests/test_field_operation_grease_duct.py`, `post_install` etiketli, 7 test:

- Yağlı kanal operasyonuna `GRD-` numarası atanması, diğer tiplerde boş kalması
- Tip sonradan değiştirildiğinde numaranın atanması
- Ölçüm satırlarının toplamının `grease_total_length` alanına yansıması
- Sertifikanın müşteri adı, numara ve erişim notunu basması (HTML)
- Türkçe etiketlerle basılması — test `tr_TR` dilini kendisi aktive edip çevirileri yükler
  (`_activate_and_install_lang`), taze veritabanında da yeşil
- PDF üretimi: `wkhtmltopdf` kurulu değilse test `skipTest` ile geçer (ortama bağlı kırmızı yok)

Çalıştırma:

```
odoo-bin -c <conf> -d <db> -u field_operation_grease_duct --test-tags /field_operation_grease_duct --stop-after-init
```

## 7. Çeviri

`i18n/tr.po` (Türkçe) ve `i18n/field_operation_grease_duct.pot` (şablon) dahildir. Sertifika
başlıkları, tablo kolonları ve seçim etiketleri Türkçeye çevrilmiştir.
