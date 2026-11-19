"""Ayarların "?" düğmesiyle açılan ayrıntılı açıklamaları.

Anahtarlar lookie_app.SETTINGS ile, değerler cihazdaki Settings.cpp ve
config.h ile aynı olmalı.
"""

DETAILS = {
    "tr": {
        "ylin": (
            "Bire bir bölge, kafanızı merkezden bu açıya kadar çevirdiğinizde oyundaki "
            "bakışın kafanızı tam olarak takip ettiği aralıktır. Bu bölgede 10° baş dönüşü "
            "oyunda da 10° bakış üretir; böylece yola ve aynalara yapılan kısa bakışlar doğal "
            "hisseder.\n\n"
            "Değeri büyütürseniz hızlanma daha geç başlar ve kamyonun arkasına bakmak için "
            "kafanızı daha fazla çevirmeniz gerekir. Değeri küçültürseniz hızlanma daha erken "
            "başlar.\n\nVarsayılan: 15°"
        ),
        "yblend": (
            "Geçiş genişliği, bire bir bölgeden sonra hassasiyetin uzak hassasiyete kadar "
            "yumuşakça arttığı baş dönüşü aralığıdır.\n\n"
            "Geniş bir geçiş hızlanmayı neredeyse fark edilmez kılar. Dar bir geçiş daha keskin "
            "bir hızlanma yaratır. 0 değeri hızlanmayı tek bir noktada, birden başlatır.\n\n"
            "Varsayılan: 15°"
        ),
        "ygain": (
            "Uzak hassasiyet, geçiş bölgesinden sonra her derecelik baş dönüşünün oyunda kaç "
            "derecelik bakış ürettiğini belirler. Örneğin 6 değerinde, geçişten sonra kafanızı "
            "5° daha çevirmek bakışı 30° döndürür.\n\n"
            "Değeri büyütürseniz kamyonun arkasını daha az baş çevirerek görürsünüz, ama uzak "
            "bölgede bakış daha oynak olur. 1 değeri eğriyi tamamen kapatır ve bakış her yerde "
            "kafanızı bire bir takip eder. Bakış en fazla 180°'ye kadar döner.\n\n"
            "Varsayılan: 6"
        ),
        "prng": (
            "Hassasiyet aralığı, yukarı-aşağı ekseninin tam sapmaya ulaşması için kafanızı kaç "
            "derece eğmeniz gerektiğini belirler. Büyük değer daha az hassas demektir.\n\n"
            "ETS2 yukarı-aşağı hareketi çok büyüttüğü için bu değer genellikle yüksek tutulur. "
            "Bu ayarı cihazdaki ayar butonuyla da değiştirebilirsiniz: butonu basılı tutup "
            "başınızı sağ omzunuza yatırmak hassasiyeti artırır, sol omzunuza yatırmak "
            "azaltır.\n\nVarsayılan: 3000°"
        ),
        "poff": (
            "Düz bakış görüşü, kafanız ortadayken oyuna gönderilen yukarı-aşağı eksen "
            "değeridir. Bu sayede düz bakarken oyunun kendi sıfır noktası yerine istediğiniz "
            "görüşü elde edersiniz; örneğin ETS2'de kamerayı direksiyonun üstüne "
            "kaldırabilirsiniz. Negatif değerler görüşü yukarı kaldırır.\n\n"
            "Bu ayarı cihazdaki ayar butonuyla da değiştirebilirsiniz: butonu basılı tutup "
            "başınızı yukarı ya da aşağı eğmek görüşü kaydırır.\n\nVarsayılan: -0,05"
        ),
        "pdz": (
            "Ölü bölge, merkezin iki yanında yok sayılan baş eğme açısıdır. Nefes alıp "
            "verirken ya da direksiyon çevirirken kafanın yaptığı küçük hareketler bu sayede "
            "görüşü oynatmaz.\n\n"
            "Kafanız bu sınırı geçtiğinde görüş sıfırdan başlayarak yumuşakça hareket eder ve "
            "sıçrama yapmaz.\n\nVarsayılan: 8°"
        ),
        "ac": (
            "Koltuk telafisi, dönen bir koltukta pedala basarken ya da vites değiştirirken "
            "koltuğun gövdenizle birlikte dönmesinden kaynaklanan kaymayı giderir. Kafanız "
            "merkeze yakın ve sakin durduğunda merkez yavaşça baktığınız yöne çekilir.\n\n"
            "Yan bakışlar ve ayna kontrolleri çalışma penceresinin dışında kaldığı için bu "
            "düzeltmeden etkilenmez. Sabit bir sandalye kullanıyorsanız özelliği "
            "kapatabilirsiniz."
        ),
        "acw": (
            "Çalışma penceresi, koltuk telafisinin devreye girdiği açı aralığıdır. Telafi "
            "yalnızca kafanız merkezin bu kadar yakınındayken çalışır.\n\n"
            "Bu değer en kısa yan bakışlarınızdan küçük olmalıdır. Aksi halde uzun süre "
            "tutulan bir yan bakış merkeze doğru çekilebilir.\n\nVarsayılan: 8°"
        ),
        "act": (
            "Telafi süresi, merkezin baktığınız yöne ne kadar hızlı çekileceğini belirleyen "
            "zaman sabitidir. Bu süre içinde bir kayma yaklaşık üçte iki oranında düzelir.\n\n"
            "Küçük değer daha güçlü bir telafi sağlar, ama pencere içinde uzun süre baktığınız "
            "bir nokta da merkeze daha hızlı kayar. Büyük değer daha yumuşak bir telafi "
            "sağlar.\n\nVarsayılan: 15 sn"
        ),
        "acd": (
            "Sakinlik sınırı, kafanın sakin sayılması için dönüş hızının kalması gereken üst "
            "sınırdır.\n\n"
            "Kafanız bundan hızlı dönüyorsa telafi durur. Böylece etrafa aktif olarak "
            "bakınırken merkez yerinden oynamaz.\n\nVarsayılan: 5 °/sn"
        ),
        "acm": (
            "Sakinlik süresi, telafinin başlaması için kafanızın sakinlik sınırının altında "
            "kalması gereken en kısa süredir.\n\n"
            "Bu süre, kısa hareketlerin arasındaki anlık duraklamalarda telafinin çalışmasını "
            "engeller.\n\nVarsayılan: 1000 ms"
        ),
        "smc": (
            "Dururken yumuşatma, kafanız hareketsizken uygulanan filtrenin kesim frekansıdır.\n\n"
            "Küçük değer, nabız ve nefesin yarattığı titremeyi daha iyi bastırır ve görüntüyü "
            "sakinleştirir, ama hareket başladığında biraz daha gecikme olur. Büyük değer "
            "daha çevik ama daha titrek bir görüntü verir.\n\nVarsayılan: 0,6 Hz"
        ),
        "smb": (
            "Hareket tepkisi, filtrenin hızlı hareketlerde ne kadar açılacağını belirler.\n\n"
            "Büyük değer hızlı baş dönüşlerinde gecikmeyi azaltır. Küçük değer daha yumuşak "
            "ama daha gecikmeli bir hareket verir.\n\nVarsayılan: 0,04"
        ),
        "adz": (
            "Sağ-sol ölü bölgesi, merkezin iki yanında sıfırda tutulan küçük açıdır. Kafanız "
            "neredeyse dururken bakışın kendi kendine titremesini engeller.\n\n"
            "Kafanız bu sınırı geçtiğinde bakış sıfırdan devam eder ve sıçrama yapmaz.\n\n"
            "Varsayılan: 0,8°"
        ),
        "rsm": (
            "Ortalama gecikmesi, ortalama butonu bırakıldıktan ne kadar sonra merkezin "
            "alınacağını belirler.\n\n"
            "Kafanızdaki butona basmak kafanızı hafifçe döndürür. Bu yüzden merkez, basma "
            "anında değil, eliniz çekilip kafanız durulduktan sonra alınır.\n\n"
            "Varsayılan: 300 ms"
        ),
    },
    "en": {
        "ylin": (
            "The one-to-one range is the angle from the center within which the view in the "
            "game follows your head exactly. In this range, a 10° head turn produces a 10° "
            "view turn, so short glances at the road and the mirrors feel natural.\n\n"
            "A larger value makes the acceleration start later, so you need to turn your head "
            "further to look behind the truck. A smaller value makes it start earlier.\n\n"
            "Default: 15°"
        ),
        "yblend": (
            "The transition width is the range of head turn beyond the one-to-one range over "
            "which the sensitivity rises smoothly to the far sensitivity.\n\n"
            "A wide transition makes the acceleration almost unnoticeable. A narrow transition "
            "makes it sharper. The value 0 starts the acceleration abruptly at a single "
            "point.\n\nDefault: 15°"
        ),
        "ygain": (
            "The far sensitivity defines how many degrees of view each degree of head turn "
            "produces beyond the transition. For example, with a value of 6, turning your head "
            "5° further turns the view by 30°.\n\n"
            "A larger value lets you see behind the truck with a smaller head turn, but the "
            "view becomes more sensitive in the far range. The value 1 turns the curve off, so "
            "the view follows your head one to one everywhere. The view turns by at most "
            "180°.\n\nDefault: 6"
        ),
        "prng": (
            "The sensitivity range defines how far you need to tilt your head for the up-down "
            "axis to reach full deflection. A larger value means less sensitivity.\n\n"
            "ETS2 strongly amplifies up-down movement, so this value is usually kept high. You "
            "can also change it with the adjust button on the device: holding the button and "
            "tilting your head toward the right shoulder increases the sensitivity, and toward "
            "the left shoulder decreases it.\n\nDefault: 3000°"
        ),
        "poff": (
            "The straight-ahead view is the up-down axis value sent to the game while your "
            "head is centered. It lets the straight-ahead view show what you want instead of "
            "the game's own zero point; in ETS2, for example, you can raise the camera above "
            "the steering wheel. Negative values raise the view.\n\n"
            "You can also change it with the adjust button on the device: holding the button "
            "and nodding up or down moves the view.\n\nDefault: -0.05"
        ),
        "pdz": (
            "The deadzone is the nod angle on either side of the center that is ignored. Small "
            "head movements while you breathe or steer therefore do not move the view.\n\n"
            "When your head passes this limit, the view starts moving smoothly from zero and "
            "does not jump.\n\nDefault: 8°"
        ),
        "ac": (
            "Chair compensation corrects the drift caused by a swivel chair turning together "
            "with your body while you press the pedals or change gear. While your head rests "
            "calm near the center, the center is slowly pulled toward where you are looking.\n\n"
            "Glances and mirror checks stay outside the working window, so they are not "
            "affected. You can turn the feature off if you use a fixed chair."
        ),
        "acw": (
            "The working window is the angle range in which chair compensation works. It only "
            "works while your head is this close to the center.\n\n"
            "Keep this value smaller than your shortest glances. Otherwise a glance that you "
            "hold for a long time may be pulled toward the center.\n\nDefault: 8°"
        ),
        "acd": (
            "The calm limit is the highest rotation speed at which your head still counts as "
            "calm.\n\n"
            "If your head turns faster than this, compensation pauses, so the center does not "
            "move while you are actively looking around.\n\nDefault: 5 °/s"
        ),
        "act": (
            "The compensation time is the time constant that defines how fast the center is "
            "pulled toward where you are looking. Within this time, a drift is corrected by "
            "about two thirds.\n\n"
            "A smaller value gives stronger compensation, but a point that you look at for a "
            "long time inside the window also drifts to the center faster. A larger value "
            "gives gentler compensation.\n\nDefault: 15 s"
        ),
        "acm": (
            "The calm time is the shortest time your head must stay below the calm limit "
            "before compensation starts.\n\n"
            "It keeps compensation from running during brief pauses between movements.\n\n"
            "Default: 1000 ms"
        ),
        "smc": (
            "Smoothing at rest is the cutoff frequency of the filter while your head is "
            "still.\n\n"
            "A smaller value suppresses the jitter from your pulse and breathing better and "
            "calms the view, but adds a little lag when you start to move. A larger value "
            "gives a quicker but more jittery view.\n\nDefault: 0.6 Hz"
        ),
        "smb": (
            "The motion response defines how much the filter opens up during fast "
            "movements.\n\n"
            "A larger value reduces the lag on fast head turns. A smaller value gives smoother "
            "but more delayed movement.\n\nDefault: 0.04"
        ),
        "adz": (
            "The left-right deadzone is the small angle on either side of the center that is "
            "held at zero. It stops the view from jittering while your head is almost "
            "still.\n\n"
            "When your head passes this limit, the view continues from zero and does not "
            "jump.\n\nDefault: 0.8°"
        ),
        "rsm": (
            "The recenter delay defines how long after the recenter button is released the "
            "center is captured.\n\n"
            "Pressing a button on your head turns your head slightly, so the center is not "
            "captured at the press but after your hand is away and your head has settled.\n\n"
            "Default: 300 ms"
        ),
    },
}
