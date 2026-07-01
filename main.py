from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from database import (
    init_db,
    save_ai_question,
    get_random_stored_question,
    get_question_by_id,
    get_question_count,
    question_exists,
    create_user,
    get_user_by_email,
    get_user_by_id,
    update_user_stats,
)
from models import (
    DiagnosticTestSubmission,
    DiagnosticResult,
    AIQuestionFormat,
    UserRegister,
    UserLogin,
    UserOut,
    TokenResponse,
    AnswerSubmission,
)
from auth import hash_password, verify_password, create_token, get_current_user_id

from fastapi import Depends

import json

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"

# Uygulama ilk açıldığında depo boşsa eklenecek akademik YDS soruları.
SEED_QUESTIONS = [
    {
        "question_text": "Due to severe structural degradation that compromised public safety, the municipal authorities ultimately decided to ------- the historic landmark.",
        "options": {"A": "demolish", "B": "construct", "C": "renovate", "D": "preserve", "E": "abandon"},
        "correct_option": "A",
        "ai_explanation": "Cümlede binanın yapısal bütünlüğünün bozulduğu ve kamu güvenliğini tehlikeye attığı belirtilerek yıkılması kararı vurgulanmıştır. 'Demolish' (yıkmak, yerle bir etmek) kelimesi bağlama tam uymaktadır.",
    },
    {
        "question_text": "Despite facing fierce condemnation from environmental groups, the committee remained ------- in its commitment to implement the controversial energy policy.",
        "options": {"A": "hesitant", "B": "resolute", "C": "ambiguous", "D": "indifferent", "E": "reluctant"},
        "correct_option": "B",
        "ai_explanation": "'Despite' bağlacı cümledeki zıtlık ilişkisini kurar: Yoğun eleştirilere rağmen komite geri adım atmamış ve kararında durmuştur. 'Resolute' (kararlı, azimli) bu zıtlığa en uygun anlamı verir.",
    },
    {
        "question_text": "The empirical evidence presented in the study was so ------- that even the most skeptical members of the scientific community were forced to acknowledge its validity.",
        "options": {"A": "trivial", "B": "compelling", "C": "questionable", "D": "obscure", "E": "premature"},
        "correct_option": "B",
        "ai_explanation": "Cümlede en şüpheci bilim insanlarının bile bulguların geçerliliğini kabul etmek zorunda kaldığı belirtiliyor; bu da kanıtların son derece güçlü olduğunu gösterir. 'Compelling' (ikna edici, güçlü) doğru seçenektir.",
    },
    {
        "question_text": "The diplomatic negotiations aimed at establishing a permanent ceasefire were severely ------- by both factions' stubborn refusal to make even the slightest compromise.",
        "options": {"A": "facilitated", "B": "hindered", "C": "accelerated", "D": "celebrated", "E": "simplified"},
        "correct_option": "B",
        "ai_explanation": "Her iki tarafın da en küçük bir taviz vermeyi bile reddetmesi, diplomatik görüşmelerin önünü tıkamış ve engellemiştir. 'Hindered' (engellenmiş, aksamış) bu olumsuz etkiyi karşılar.",
    },
    {
        "question_text": "Although the forensic evidence brought forward during the high-profile trial was largely -------, the jury still deemed it substantial enough to reach a unanimous verdict.",
        "options": {"A": "circumstantial", "B": "conclusive", "C": "irrelevant", "D": "fabricated", "E": "redundant"},
        "correct_option": "A",
        "ai_explanation": "'Although' zıtlık kurar: Kanıtların doğrudan veya kesin olmamasına (dolaylı olmasına) rağmen jüri karar vermek için yeterli bulmuştur. 'Circumstantial' (dolaylı, karineye dayalı) bu zıtlığa uyar.",
    },
    {
        "question_text": "The multinational corporation's net revenues have experienced a ------- decline over the past fiscal year, sparking widespread anxiety among its primary shareholders.",
        "options": {"A": "negligible", "B": "marginal", "C": "steady", "D": "momentary", "E": "reversible"},
        "correct_option": "C",
        "ai_explanation": "Yatırımcıları ve hissedarları endişelendiren uzun süreli bir gerileme, anlık değil sürekli bir düşüşü işaret eder. 'Steady' (istikrarlı, sürekli) doğru seçenektir.",
    },
    {
        "question_text": "The applicant's exceptional ------- to historical accuracy rendered her the ideal candidate for the institute's highly meticulous archival project.",
        "options": {"A": "indifference", "B": "attention", "C": "aversion", "D": "resistance", "E": "neglect"},
        "correct_option": "B",
        "ai_explanation": "Titiz bir arşiv projesi için ideal aday olmasının sebebi detaylara ve doğruluğa verdiği önemdir. 'Attention to' (dikkat, özen) kalıbı bağlama tam uyar.",
    },
    {
        "question_text": "The stringent environmental frameworks ratified by the European council are specifically intended to ------- toxic emission levels in metropolitan areas over the next decade.",
        "options": {"A": "exacerbate", "B": "mitigate", "C": "ignore", "D": "publicize", "E": "complicate"},
        "correct_option": "B",
        "ai_explanation": "Yeni çevre düzenlemelerinin ve yasal çerçevelerin amacı hava kirliliğini ve emisyonları azaltmaktır. 'Mitigate' (hafifletmek, etkisini azaltmak) bu amaca uygun düşer.",
    },
    {
        "question_text": "The philosophical treatise was written in such a ------- style that even advanced scholars struggled to grasp its central thesis.",
        "options": {"A": "lucid", "B": "convoluted", "C": "concise", "D": "engaging", "E": "rehearsed"},
        "correct_option": "B",
        "ai_explanation": "İleri düzey akademisyenlerin bile ana fikri kavramakta zorlanması eserin son derece karmaşık olduğunu gösterir. 'Convoluted' (karmaşık, dolambaçlı) doğru seçenektir.",
    },
    {
        "question_text": "The administration's unilateral decision to downsize the corporate budget was met with fierce ------- from staff members who anticipated imminent layoffs.",
        "options": {"A": "enthusiasm", "B": "apathy", "C": "resistance", "D": "approval", "E": "gratitude"},
        "correct_option": "C",
        "ai_explanation": "İşten çıkarılma korkusu yaşayan çalışanların bütçe kesintilerine tepkisi olumsuz olacaktır. 'Resistance' (direniş, karşı çıkma) bu durumla tutarlıdır.",
    },
    {
        "question_text": "Dating back to the early medieval period, the recovery of the papyrus scroll was so ------- that conservationists had to use specialized tools to prevent its disintegration.",
        "options": {"A": "durable", "B": "fragile", "C": "ordinary", "D": "replicated", "E": "abundant"},
        "correct_option": "B",
        "ai_explanation": "Özel araçlar kullanılmasını gerektirecek kadar hassas olan ve dağılma tehlikesi bulunan tarihi eser kırılgandır. 'Fragile' (kırılgan, hassas) doğru seçenektir.",
    },
    {
        "question_text": "The testimony provided by the key witness was entirely ------- with the forensic evidence uncovered at the crime scene, thereby undermining the prosecution's case.",
        "options": {"A": "consistent", "B": "compatible", "C": "inconsistent", "D": "aligned", "E": "synchronized"},
        "correct_option": "C",
        "ai_explanation": "Tanık ifadesinin iddiaları zayıflatması ve şüphe uyandırması, fiziksel ve adli kanıtlarla çelişmesinden kaynaklanır. 'Inconsistent' (tutarsız, çelişen) bu durumu ifade eder.",
    },
    {
        "question_text": "The research laboratory's rapid breakthrough in biotechnology can be primarily attributed to its ------- approach to synthesizing complex organic molecules.",
        "options": {"A": "conventional", "B": "innovative", "C": "outdated", "D": "indecisive", "E": "passive"},
        "correct_option": "B",
        "ai_explanation": "Biyoteknoloji alanındaki hızlı gelişme ve başarının arkasındaki temel neden çağdaş ve yenilikçi yöntemlerdir. 'Innovative' (yenilikçi) bağlama en uygun kelimedir.",
    },
    {
        "question_text": "The senator was widely criticized as being ------- after shifting his ideological stance on public taxation multiple times within a single legislative session.",
        "options": {"A": "consistent", "B": "principled", "C": "opportunistic", "D": "transparent", "E": "diplomatic"},
        "correct_option": "C",
        "ai_explanation": "Kısa süre içinde duruşunu ve fikirlerini defalarca değiştiren bir siyasetçi, ilkesizce çıkarlara göre hareket etmekle suçlanır. 'Opportunistic' (fırsatçı) doğru seçenektir.",
    },
    {
        "question_text": "The experimental sedative produced a highly ------- effect on the trial participants, inducing a state of profound drowsiness that persisted for several hours.",
        "options": {"A": "negligible", "B": "pronounced", "C": "delayed", "D": "reversible", "E": "imaginary"},
        "correct_option": "B",
        "ai_explanation": "Saatlerce süren derin bir uyuşukluk hali, ilacın vücut üzerinde çok bariz ve güçlü bir etkisi olduğunu gösterir. 'Pronounced' (belirgin, çok net hissedilen) bağlama uyar.",
    },
    {
        "question_text": "The museum's new permanent exhibit aims to ------- visitors about the often-overlooked cultural contributions of indigenous tribes.",
        "options": {"A": "entertain", "B": "enlighten", "C": "confuse", "D": "discourage", "E": "distract"},
        "correct_option": "B",
        "ai_explanation": "Sergi, genelde göz ardı edilen ve bilinmeyen bir tarihi ziyaretçilere öğretmeyi ve onları bilgilendirmeyi amaçlamaktadır. 'Enlighten' (aydınlatmak, bilgilendirmek) doğru seçenektir.",
    },
    {
        "question_text": "The unprecedented success of the deep-sea exploration mission was largely ------- to the integration of cutting-edge sonar technology.",
        "options": {"A": "attributable", "B": "irrelevant", "C": "opposed", "D": "indifferent", "E": "unrelated"},
        "correct_option": "A",
        "ai_explanation": "Derin deniz keşif misyonunun başarısının arkasındaki sebebin yeni sonar teknolojileri olduğu ifade edilmiştir. 'Attributable to' (bir şeye bağlanabilir, atfedilebilir) kalıbı bağlama uyar.",
    },
    {
        "question_text": "The international monetary body warned that the sudden collapse of real estate prices could have ------- consequences for developing economies.",
        "options": {"A": "beneficial", "B": "dire", "C": "negligible", "D": "predictable", "E": "favorable"},
        "correct_option": "B",
        "ai_explanation": "Ekonomik bir kuruluş tarafından yapılan uyarı söz konusu olduğundan, sonuçların son derece olumsuz olması beklenir. 'Dire' (vahim, korkunç, çok ciddi) bu uyarıyla tutarlıdır.",
    },
    {
        "question_text": "The novelist's debut avant-garde manuscript was initially ------- by mainstream critics, only to achieve widespread literary acclaim decades later.",
        "options": {"A": "praised", "B": "dismissed", "C": "celebrated", "D": "rewarded", "E": "promoted"},
        "correct_option": "B",
        "ai_explanation": "Cümlenin sonundaki 'yıllar sonra büyük övgü aldı' ifadesiyle kurulan zıtlık, eserin başlangıçta eleştirmenler tarafından ciddiye alınmadığını gösterir. 'Dismissed' (göz ardı edilmiş, reddedilmiş) doğru seçenektir.",
    },
    {
        "question_text": "The comprehensive administrative reforms were specifically designed to ------- unnecessary bureaucratic obstacles and expedite the regulatory approval process.",
        "options": {"A": "perpetuate", "B": "eliminate", "C": "justify", "D": "complicate", "E": "ignore"},
        "correct_option": "B",
        "ai_explanation": "Onay sürecini hızlandırmak ve bürokrasiyi azaltmak için aradaki engellerin yok edilmesi gerekir. 'Eliminate' (ortadan kaldırmak, bertaraf etmek) bu amaca uygundur.",
    },
    {
        "question_text": "Epidemiological studies indicate that prolonged occupational exposure to high-intensity acoustic environments can permanently ------- auditory sensitivity.",
        "options": {"A": "enhance", "B": "restore", "C": "impair", "D": "maintain", "E": "develop"},
        "correct_option": "C",
        "ai_explanation": "Yüksek gürültülü ortamlara uzun süre maruz kalmanın işitme duyusuna ve sağlığına vereceği zarar anlatılmaktadır. 'Impair' (bozmak, zayıflatmak, zarar vermek) bu olumsuz etkiyi ifade eder.",
    },
    {
        "question_text": "The diplomat's highly ------- response to inquiries regarding the border dispute left international observers deeply skeptical of her government's true intentions.",
        "options": {"A": "straightforward", "B": "evasive", "C": "enthusiastic", "D": "detailed", "E": "sincere"},
        "correct_option": "B",
        "ai_explanation": "Uluslararası gözlemcilerin hükümetin niyetinden şüphe etmesi, verilen cevabın net olmadığını, konuyu saptırmaya yönelik olduğunu gösterir. 'Evasive' (kaçamak, kaçınan) doğru seçenektir.",
    },
    {
        "question_text": "The extensive trans-continental railway network was constructed to ------- isolated commercial hubs that had been geographically separated for generations.",
        "options": {"A": "divide", "B": "connect", "C": "isolate", "D": "distinguish", "E": "compare"},
        "correct_option": "B",
        "ai_explanation": "Demiryolu ağının coğrafi olarak birbirinden ayrı kalmış ticari merkezleri bir araya getirme işlevi vurgulanmaktadır. 'Connect' (bağlamak, birleştirmek) doğru seçenektir.",
    },
    {
        "question_text": "The playwright's latest theatrical production received ------- reviews from contemporary critics, who universally lauded its dramatic depth and stylistic originality.",
        "options": {"A": "mixed", "B": "scathing", "C": "mediocre", "D": "lukewarm", "E": "glowing"},
        "correct_option": "E",
        "ai_explanation": "Eleştirmenlerin eserin derinliğini ve özgünlüğünü tüm dünyada övmesi çok olumlu bir durumdur. 'Glowing' (coşkulu, çok olumlu, övgü dolu) bu durumla tutarlıdır.",
    },
    {
        "question_text": "Climatologists are actively developing advanced mitigation strategies to ------- the adverse long-term impacts of global greenhouse gas accumulations.",
        "options": {"A": "intensify", "B": "counteract", "C": "overlook", "D": "celebrate", "E": "duplicate"},
        "correct_option": "B",
        "ai_explanation": "Bilim insanlarının amacı sera gazlarının olumsuz etkilerini nötrlemek ve bu etkilere karşı koymaktır. 'Counteract' (etkisini gidermek, karşı koymak) bu amaca tam uyar.",
    },
    {
        "question_text": "The newly appointed director's remarkably ------- administrative philosophy encouraged researchers to collaborate across disciplines and undertake innovative risks.",
        "options": {"A": "authoritarian", "B": "rigid", "C": "inclusive", "D": "indifferent", "E": "distant"},
        "correct_option": "C",
        "ai_explanation": "Çanşanları fikir paylaşmaya ve disiplinler arası çalışmaya teşvik eden yönetim tarzı kapsayıcı olmalıdır. 'Inclusive' (kapsayıcı, kucaklayıcı) doğru seçenektir.",
    },
    {
        "question_text": "The non-governmental organization's core mandate is to ------- the constitutional rights of marginalized populations through extensive legal advocacy.",
        "options": {"A": "undermine", "B": "uphold", "C": "suppress", "D": "ignore", "E": "question"},
        "correct_option": "B",
        "ai_explanation": "Sivil toplum kuruluşunun amacı azınlıkların ve dezavantajlı grupların anayasal haklarını savunmak ve korumaktır. 'Uphold' (savunmak, desteklemek, korumak) doğru seçenektir.",
    },
    {
        "question_text": "The patient's remarkably rapid physiological ------- following the complex neurosurgical intervention astonished the entire medical board.",
        "options": {"A": "deterioration", "B": "recovery", "C": "withdrawal", "D": "confusion", "E": "isolation"},
        "correct_option": "B",
        "ai_explanation": "Ağır bir beyin ameliyatının ardından tıp heyetini şaşırtacak derecede olumlu giden durum hastanın iyileşme hızıdır. 'Recovery' (iyileşme, toparlanma) doğru seçenektir.",
    },
    {
        "question_text": "The novelist's prose is celebrated for its ------- imagery, which effortlessly evokes a profound emotional response from the reader.",
        "options": {"A": "vague", "B": "sparse", "C": "vivid", "D": "dull", "E": "repetitive"},
        "correct_option": "C",
        "ai_explanation": "Okuyucuda derin bir duygusal karşılık uyandıran ve zihinde net resimler çizen tasvirler canlı ve etkilidir. 'Vivid' (canlı, parlak, net) doğru seçenektir.",
    },
    {
        "question_text": "The United Nations attempted to ------- the two warring factions, but the deep-rooted ethnic animosity hindered any permanent peace agreement.",
        "options": {"A": "alienate", "B": "reconcile", "C": "provoke", "D": "separate", "E": "eliminate"},
        "correct_option": "B",
        "ai_explanation": "Derin düşmanlıkların barışı engellediği bir bağlamda, uluslararası kuruluşun amacı tarafları uzlaştırmaya çalışmaktır. 'Reconcile' (uzlaştırmak, barıştırmak) doğru seçenektir.",
    },
    {
        "question_text": "Despite remaining an ------- settlement for centuries, the coastal town transformed into a bustling tourist hub after its inclusion in a historical documentary.",
        "options": {"A": "overcrowded", "B": "prosperous", "C": "obscure", "D": "accessible", "E": "celebrated"},
        "correct_option": "C",
        "ai_explanation": "'Despite' bağlacı zıtlık ister: Kasaba önceleri hiç bilinmezken belgeselden sonra popüler olmuştur. 'Obscure' (bilinmeyen, tanınmamış, ücra) bu zıtlığı kurar.",
    },
    {
        "question_text": "The international court declared that the bilateral maritime treaty was ------- because crucial clauses had been signed under political coercion.",
        "options": {"A": "binding", "B": "void", "C": "valid", "D": "enforceable", "E": "transparent"},
        "correct_option": "B",
        "ai_explanation": "Baskı ve zorlama altında imzalanan uluslararası anlaşmalar hukuken geçersiz sayılır. 'Void' (hükümsüz, geçersiz) kelimesi yasal bağlama tam uyar.",
    },
    {
        "question_text": "The construction of the industrial complex will inevitably ------- the fragile subterranean ecosystems of several protected cave-dwelling species.",
        "options": {"A": "restore", "B": "disrupt", "C": "preserve", "D": "improve", "E": "expand"},
        "correct_option": "B",
        "ai_explanation": "Büyük bir sanayi tesisinin kurulması, bölgedeki hassas yeraltı ekosistemlerine ve canlılara zarar verecektir. 'Disrupt' (bozmak, altüst etmek) doğru seçenektir.",
    },
    {
        "question_text": "The primary objective of the latest security software patch is to ------- the cryptographic vulnerabilities that remote hackers have recently been exploiting.",
        "options": {"A": "create", "B": "expose", "C": "patch", "D": "ignore", "E": "publicize"},
        "correct_option": "C",
        "ai_explanation": "Yazılım güncellemelerinin amacı sistemdeki açıkları ve gedikleri kapatmaktır. 'Patch' (yamamak, kapatmak) teknik bağlamda doğru kelimedir.",
    },
    {
        "question_text": "The geological data gathered from the volcanic site was so ------- that researchers found it impossible to construct a logical timeline of eruptions.",
        "options": {"A": "detailed", "B": "comprehensive", "C": "fragmented", "D": "organized", "E": "accessible"},
        "correct_option": "C",
        "ai_explanation": "Düzenli bir zaman çizelgesi oluşturmayı imkânsız kılan veri yapısı eksik ve kopuk olmalıdır. 'Fragmented' (parçalı, kesintili, bütünlüğü olmayan) doğru seçenektir.",
    },
    {
        "question_text": "The neighboring sovereigns signed a ------- trade alliance designed to optimize custom procedures and minimize cross-border economic tariffs.",
        "options": {"A": "unilateral", "B": "bilateral", "C": "internal", "D": "confidential", "E": "temporary"},
        "correct_option": "B",
        "ai_explanation": "İki komşu ülke arasında yapılan ticaret anlaşması iki taraflıdır. 'Bilateral' (iki taraflı, ikili) doğru seçenektir."
    },
    {
        "question_text": "The sociologists advanced a ------- theory regarding urban isolation that continues to reshape sociological research two centuries later.",
        "options": {"A": "irrelevant", "B": "outdated", "C": "profound", "D": "simplistic", "E": "contradictory"},
        "correct_option": "C",
        "ai_explanation": "İki yüz yıl sonra bile araştırmaları şekillendiren fikirler çok derin ve etkili olmalıdır. 'Profound' (derin, büyük etkili) doğru seçenektir."
    },
    {
        "question_text": "The logistics firm decided to ------- its supply chain network into East Asia to tap into emerging consumer markets.",
        "options": {"A": "reduce", "B": "suspend", "C": "expand", "D": "relocate", "E": "evaluate"},
        "correct_option": "C",
        "ai_explanation": "Yeni pazarlara ve ülkelere açılmak operasyonların büyütülmesi anlamına gelir. 'Expand' (genişletmek, büyütmek) doğru seçenektir."
    },
    {
        "question_text": "The investigative report successfully sought to ------- the long-standing misconceptions about the cause of the economic crisis.",
        "options": {"A": "reinforce", "B": "debunk", "C": "create", "D": "celebrate", "E": "promote"},
        "correct_option": "B",
        "ai_explanation": "Bir raporun veya araştırmanın efsaneler/mitler karşısındaki amacı onların yanlışlığını kanıtlamaktır. 'Debunk' (çürütmek, maskesini düşürmek) doğru kelimedir."
    },
    {
        "question_text": "Medical humanitarian teams worked ------- in the disaster zone to prevent the spread of infectious diseases after the flood.",
        "options": {"A": "reluctantly", "B": "tirelessly", "C": "carelessly", "D": "occasionally", "E": "indifferently"},
        "correct_option": "B",
        "ai_explanation": "Afet bölgesinde canla başla çalışan ekiplerin yorulmadan mücadele ettiği vurgulanmaktadır. 'Tirelessly' (yorulmaksızın, canla başla) doğru seçenektir."
    },
    {
        "question_text": "The laboratory's innovative research on stem cells has ------- new avenues for personalized medicine and gene therapy.",
        "options": {"
