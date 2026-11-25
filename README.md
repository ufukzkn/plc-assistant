# PLC Assistant

Omron CJ2M için deneysel, salt okunur program inceleme ve arıza asistanı. Çevrimdışı BIN çözümleme, USB üzerinden FINS okuma, çıkış ayrıntısı ve Türkçe soru önerileri sunar.

## Windows kurulumu

Windows Gezgini’nde repo klasöründeki **BASLAT.bat** dosyasına çift tıklayın. Başlatıcı önce repo içindeki `.venv` ortamını, ardından Windows Python başlatıcısını (`py -3`) veya sistemdeki `python` komutunu kullanır.

- Git ve Python 3.10 veya üzeri gerekir. Python kurulumunda Tcl/Tk bileşenini etkin tutun.
- Canlı USB okuması için Windows, Omron CX-Server Lite, Omron USB sürücüsü ve tek PLC içeren bir CDM dosyası gerekir. Mevcut PowerShell köprüsü 32 bit CX-Server Lite DLL'ini kullanır. DLL yolu `session.ps1` ve `bridge.ps1` içinde tanımlıdır.
- Çevrimdışı BIN açma, öneriler ve sentetik testler için PLC bağlantısı gerekmez.

PowerShell'de ilk kurulum:

```powershell
git clone https://github.com/ufukzkn/plc-assistant.git
cd plc-assistant
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Aynı repoyu daha önce klonladıysanız, repo klasöründe güncelleyin ve `BASLAT.bat` dosyasına çift tıklayın:

```powershell
git pull --ff-only
```

## Türkçe soru önerileri

Ana ekrandaki arıza asistanı ve ayrıntı penceresindeki sohbet yazarken öneri gösterir. `çalı` veya `cali` yazınca **çalışıyor mu?** önerilir. `CIO110.00 çalı` adresi korur. Açık ayrıntı penceresindeki veya ana listede seçili olan satır soru için bağlam sağlar. Ana ekranda bir satır seçili değilse soruya bir PLC adresi ekleyin.

Öneriyi tıklayın veya Tab ile ilk seçeneği doldurun. Ok tuşlarıyla bir öneriyi işaretleyip Enter ile doldurabilirsiniz. Doldurulan soruyu Enter ile gönderin. Esc önerileri kapatır. Öneri seçilince PLC okuması tetiklenmez.

Öneriler, `question_corpus.py` içindeki örnek ifadeler ve eş anlamlılar ile yüklenen programın tanımlı adres ve etiketlerinden gelir. Türkçe karakter varyasyonları ve bazı tek harf hataları desteklenir. Arama yerelde çalışır. Canlı durum yanıtı, mevcut FINS okumasına dayanır.

## Test ve karşılaştırma

```powershell
.\.venv\Scripts\python.exe -m unittest -v
.\.venv\Scripts\python.exe check_compatibility.py --baseline "C:\eski-surum\PLC_Assistant_V402"
.\.venv\Scripts\python.exe benchmark.py
```

İkinci komut için orijinal V4.0.2 ZIP'ini ayrı bir klasöre çıkarın. Karşılaştırma aynı sentetik BIN ve FINS verileriyle adresleri, mantık çözümünü, ham yanıtları, istatistikleri, hata durumlarını ve eski soru yanıtlarını sınar. Arayüz testleri bir Tk ekranı ister. Orijinal CJ2M referans BIN ile canlı Windows/USB yolu saha doğrulamasına tabidir.
