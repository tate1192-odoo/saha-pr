# Field Operation Resequence

> Field operation numaralarını sıkı numaraya çeviren yönetici sihirbazı
> Softteknik Bilişim · Odoo 19 · AGPL-3 · sürüm `19.0.1.0.0`

## 1. Genel Bakış

`field.operation` kayıtlarının referansları hatalı veya boşluklu olduğunda bu modül
tüm aktif ve arşiv kayıtları `create_date asc, id asc` sırasıyla yeniden
numaralandırır. Numara biçimi mevcut `field.operation` serisinden alınır ve sayaç
`N + 1` değerine getirilir.

Örnek: seri `FO/` prefix ve `5` padding kullanıyorsa üç kayıt
`FO/00001`, `FO/00002`, `FO/00003` olur; bir sonraki kayıt `FO/00004` alır.

**Geri dönüş uyarısı:** Eski referanslar basılı belgelerde, e-postalarda veya dış
sistemlerde metin olarak kalmaya devam eder. İşlem sırasında yeni field operation
oluşturulmamalı veya düzenlenmemelidir.

## 2. Kapsam ve Güvenlik

- Kayıt seçimi ve önizleme yoktur; sihirbaz tüm kayıtları işler.
- Aktif ve arşiv kayıtlar dahildir.
- Kullanıcının yetkili olduğu tüm şirketlere erişimi ve tüm kayıtları görebilmesi
  gerekir.
- Erişim `field_operation.service_group_all` grubuyla sınırlıdır. Bu grubu
  `service_group_manager` miras alır; normal `service_group_user` erişemez.
- `action_resequence` işlem öncesi wizard üzerinde yazma yetkisini tekrar doğrular.

Global seri kullanıldığı için kayıtların yalnızca bir bölümü numaralandırılamaz.
Kısıtlayıcı bir record rule veya erişimi olmayan bir şirket varsa işlem reddedilir.

## 3. Seri Gereksinimleri

Wizard şu koşulları sağlayan tek bir seri bekler:

- `code = field.operation`
- aktif ve global (`company_id = False`)
- `use_date_range = False`
- `number_increment = 1`

Farklı sayıda seri, şirkete özel seri, tarih aralığı serisi veya farklı artış
adımı varsa işlem güvenli şekilde reddedilir. Prefix, suffix ve padding mevcut seri
ayarlarından korunur.

## 4. Akış

1. `field.operation` listesindeki **Resequence Field Operations** aksiyonu wizard'i
   açar.
2. Wizard işlenecek kayıt sayısını gösterir ve kalıcı değişiklik uyarısı verir.
3. **Start Resequence** onaylanır.
4. Seri kaydı ve mevcut operation kayıtları kilitlenir.
5. Kayıtlar `create_date asc, id asc` sırasıyla `1..N` numaralarıyla yazılır.
6. Eşzamanlı kayıt oluşumu veya seri numarası tüketimi tespit edilirse işlem
   geri alınır ve kullanıcıya tekrar deneme mesajı gösterilir.
7. Seri sayacı `N + 1` yapılır ve istemci yenilenir.

## 5. Dosyalar

- `wizard/field_operation_resequence_wizard.py`: wizard modeli ve işlevsel kod
- `views/field_operation_resequence_wizard_views.xml`: form ve bağlı aksiyon
- `security/ir.model.access.csv`: Head Office/Admin ACL
- `tests/test_field_operation_resequence.py`: regresyon ve yetki testleri

## 6. Testler

Testler şu davranışları doğrular:

- aktif ve arşiv kayıtların sıkı numaralanması
- seri sayacının `N + 1` yapılması
- aynı `create_date` değerinde `id` sırasının kullanılması
- ikinci çalıştırmanın aynı sonucu vermesi
- boş liste durumunda sayacın `1` yapılması
- normal ofis kullanıcısının erişim reddi
- erişimi olmayan şirket kayıtları varsa işlemin reddi
- desteklenmeyen seri yapılandırmasının reddi
