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
        "ai_explanation": "Cümlede binanın yapısal bütünlüğünün bozulduğu ve kamu güvenliğini tehlikeye attığı belirtilerek yıkılması kararı vurgulanmıştır. 'Demolish' (yıkmak, yerle bir etmek) kelimesi bağlama tam uymaktadır."
    },
    {
        "question_text": "Despite facing fierce condemnation from environmental groups, the committee remained ------- in its commitment to implement the controversial energy policy.",
        "options": {"A": "hesitant", "B": "resolute", "C": "ambiguous", "D": "indifferent", "E": "reluctant"},
        "correct_option": "B",
        "ai_explanation": "'Despite' bağlacı cümledeki zıtlık ilişkisini kurar: Yoğun eleştirilere rağmen komite geri adım atmamış ve kararında durmuştur. 'Resolute' (kararlı, azimli) bu zıtlığa en uygun anlamı verir."
    },
    {
        "question_text": "The empirical evidence presented in the study was so ------- that even the most skeptical members of the scientific community were forced to acknowledge its validity.",
        "options": {"A": "trivial", "B": "compelling", "C": "questionable", "D": "obscure", "E": "premature"},
        "correct_option": "B",
        "ai_explanation": "Cümlede en şüpheci bilim insanlarının bile bulguların geçerliliğini kabul etmek zorunda kaldığı belirtiliyor; bu da kanıtların son derece güçlü olduğunu gösterir. 'Compelling' (ikna edici, güçlü) doğru seçenektir."
    },
    {
        "question_text": "The diplomatic negotiations aimed at establishing a permanent ceasefire were severely ------- by both factions' stubborn refusal to make even the slightest compromise.",
        "options": {"A": "facilitated", "B": "hindered", "C": "accelerated", "D": "celebrated", "E": "simplified"},
        "correct_option": "B",
        "ai_explanation": "Her iki tarafın da en küçük bir taviz vermeyi bile reddetmesi, diplomatik görüşmelerin önünü tıkamış ve engellemiştir. 'Hindered' (engellenmiş, aksamış) bu olumsuz etkiyi karşılar."
    },
    {
        "question_text": "Although the forensic evidence brought forward during the high-profile trial was largely -------, the jury still deemed it substantial enough to reach a unanimous verdict.",
        "options": {"A": "circumstantial", "B": "conclusive", "C": "irrelevant", "D": "fabricated", "E": "redundant"},
        "correct_option": "A",
        "ai_explanation": "'Although' zıtlık kurar: Kanıtların doğrudan veya kesin olmamasına (dolaylı olmasına) rağmen jüri karar vermek için yeterli bulmuştur. 'Circumstantial' (dolaylı, karineye dayalı) bu zıtlığa uyar."
    },
    {
        "question_text": "The multinational corporation's net revenues have experienced a ------- decline over the past fiscal year, sparking widespread anxiety among its primary shareholders.",
        "options": {"A": "negligible", "B": "marginal", "C": "steady", "D": "momentary", "E": "reversible"},
        "correct_option": "C",
        "ai_explanation": "Yatırımcıları ve hissedarları endişelendiren uzun süreli bir gerileme, anlık değil sürekli bir düşüşü işaret eder. 'Steady' (istikrarlı, sürekli) doğru seçenektir."
    },
    {
        "question_text": "The applicant's exceptional ------- to historical accuracy rendered her the ideal candidate for the institute's highly meticulous archival project.",
        "options": {"A": "indifference", "B": "attention", "C": "aversion", "D": "resistance", "E": "neglect"},
        "correct_option": "B",
        "ai_explanation": "Titiz bir arşiv projesi için ideal aday olmasının sebebi detaylara ve doğruluğa verdiği önemdir. 'Attention to' (dikkat, özen) kalıbı bağlama tam uyar."
    },
    {
        "question_text": "The stringent environmental frameworks ratified by the European council are specifically intended to ------- toxic emission levels in metropolitan areas over the next decade.",
        "options": {"A": "exacerbate", "B": "mitigate", "C": "ignore", "D": "publicize", "E": "complicate"},
        "correct_option": "B",
        "ai_explanation": "Yeni çevre düzenlemelerinin ve yasal çerçevelerin amacı hava kirliliğini ve emisyonları azaltmaktır. 'Mitigate' (hafifletmek, etkisini azaltmak) bu amaca uygun düşer."
    },
    {
        "question_text": "The philosophical treatise was written in such a ------- style that even advanced scholars struggled to grasp its central thesis.",
        "options": {"A": "lucid", "B": "convoluted", "C": "concise", "D": "engaging", "E": "rehearsed"},
        "correct_option": "B",
        "ai_explanation": "İleri düzey akademisyenlerin bile ana fikri kavramakta zorlanması eserin son derece karmaşık olduğunu gösterir. 'Convoluted' (karmaşık, dolambaçlı) doğru seçenektir."
    },
    {
        "question_text": "The administration's unilateral decision to downsize the corporate budget was met with fierce ------- from staff members who anticipated imminent layoffs.",
        "options": {"A": "enthusiasm", "B": "apathy", "C": "resistance", "D": "approval", "E": "gratitude"},
        "correct_option": "C",
        "ai_explanation": "İşten çıkarılma korkusu yaşayan çalışanların bütçe kesintilerine tepkisi olumsuz olacaktır. 'Resistance' (direniş, karşı çıkma) bu durumla tutarlıdır."
    },
    {
        "question_text": "Dating back to the early medieval period, the recovery of the papyrus scroll was so ------- that conservationists had to use specialized tools to prevent its disintegration.",
        "options": {"A": "durable", "B": "fragile", "C": "ordinary", "D": "replicated", "E": "abundant"},
        "correct_option": "B",
        "ai_explanation": "Özel araçlar kullanılmasını gerektirecek kadar hassas olan ve dağılma tehlikesi bulunan tarihi eser kırılgandır. 'Fragile' (kırılgan, hassas) doğru seçenektir."
    },
    {
        "question_text": "The testimony provided by the key witness was entirely ------- with the forensic evidence uncovered at the crime scene, thereby undermining the prosecution's case.",
        "options": {"A": "consistent", "B": "compatible", "C": "inconsistent", "D": "aligned", "E": "synchronized"},
        "correct_option": "C",
        "ai_explanation": "Tanık ifadesinin iddiaları zayıflatması ve şüphe uyandırması, fiziksel ve adli kanıtlarla çelişmesinden kaynaklanır. 'Inconsistent' (tutarsız, çelişen) bu durumu ifade eder."
    },
    {
        "question_text": "The research laboratory's rapid breakthrough in biotechnology can be primarily attributed to its ------- approach to synthesizing complex organic molecules.",
        "options": {"A": "conventional", "B": "innovative", "C": "outdated", "D": "indecisive", "E": "passive"},
        "correct_option": "B",
        "ai_explanation": "Biyoteknoloji alanındaki hızlı gelişme ve başarının arkasındaki temel neden çağdaş ve yenilikçi yöntemlerdir. 'Innovative' (yenilikçi) bağlama en uygun kelimedir."
    },
    {
        "question_text": "The senator was widely criticized as being ------- after shifting his ideological stance on public taxation multiple times within a single legislative session.",
        "options": {"A": "consistent", "B": "principled", "C": "opportunistic", "D": "transparent", "E": "diplomatic"},
        "correct_option": "C",
        "ai_explanation": "Kısa süre içinde duruşunu ve fikirlerini defalarca değiştiren bir siyasetçi, ilkesizce çıkarlara göre hareket etmekle suçlanır. 'Opportunistic' (fırsatçı) doğru seçenektir."
    },
    {
        "question_text": "The experimental sedative produced a highly ------- effect on the trial participants, inducing a state of profound drowsiness that persisted for several hours.",
        "options": {"A": "negligible", "B": "pronounced", "C": "delayed", "D": "reversible", "E": "imaginary"},
        "correct_option": "B",
        "ai_explanation": "Saatlerce süren derin bir uyuşukluk hali, ilacın vücut üzerinde çok bariz ve güçlü bir etkisi olduğunu gösterir. 'Pronounced' (belirgin, çok net hissedilen) bağlama uyar."
    },
    {
        "question_text": "The museum's new permanent exhibit aims to ------- visitors about the often-overlooked cultural contributions of indigenous tribes.",
        "options": {"A": "entertain", "B": "enlighten", "C": "confuse", "D": "discourage", "E": "distract"},
        "correct_option": "B",
        "ai_explanation": "Sergi, genelde göz ardı edilen ve bilinmeyen bir tarihi ziyaretçilere öğretmeyi ve onları bilgilendirmeyi amaçlamaktadır. 'Enlighten' (aydınlatmak, bilgilendirmek) doğru seçenektir."
    },
    {
        "question_text": "The unprecedented success of the deep-sea exploration mission was largely ------- to the integration of cutting-edge sonar technology.",
        "options": {"A": "attributable", "B": "irrelevant", "C": "opposed", "D": "indifferent", "E": "unrelated"},
        "correct_option": "A",
        "ai_explanation": "Derin deniz keşif misyonunun başarısının arkasındaki sebebin yeni sonar teknolojileri olduğu ifade edilmiştir. 'Attributable to' (bir şeye bağlanabilir, atfedilebilir) kalıbı bağlama uyar."
    },
    {
        "question_text": "The international monetary body warned that the sudden collapse of real estate prices could have ------- consequences for developing economies.",
        "options": {"A": "beneficial", "B": "dire", "C": "negligible", "D": "predictable", "E": "favorable"},
        "correct_option": "B",
        "ai_explanation": "Ekonomik bir kuruluş tarafından yapılan uyarı söz konusu olduğundan, sonuçların son derece olumsuz olması beklenir. 'Dire' (vahim, korkunç, çok ciddi) bu uyarıyla tutarlıdır."
    },
    {
        "question_text": "The novelist's debut avant-garde manuscript was initially ------- by mainstream critics, only to achieve widespread literary acclaim decades later.",
        "options": {"A": "praised", "B": "dismissed", "C": "celebrated", "D": "rewarded", "E": "promoted"},
        "correct_option": "B",
        "ai_explanation": "Cümlenin sonundaki 'yıllar sonra büyük övgü aldı' ifadesiyle kurulan zıtlık, eserin başlangıçta eleştirmenler tarafından ciddiye alınmadığını gösterir. 'Dismissed' (göz ardı edilmiş, reddedilmiş) doğru seçenektir."
    },
    {
        "question_text": "The comprehensive administrative reforms were specifically designed to ------- unnecessary bureaucratic obstacles and expedite the regulatory approval process.",
        "options": {"A": "perpetuate", "B": "eliminate", "C": "justify", "D": "complicate", "E": "ignore"},
        "correct_option": "B",
        "ai_explanation": "Onay sürecini hızlandırmak ve bürokrasiyi azaltmak için aradaki engellerin yok edilmesi gerekir. 'Eliminate' (ortadan kaldırmak, bertaraf etmek) bu amaca uygundur."
    },
    {
        "question_text": "Epidemiological studies indicate that prolonged occupational exposure to high-intensity acoustic environments can permanently ------- auditory sensitivity.",
        "options": {"A": "enhance", "B": "restore", "C": "impair", "D": "maintain", "E": "develop"},
        "correct_option": "C",
        "ai_explanation": "Yüksek gürültülü ortamlara uzun süre maruz kalmanın işitme duyusuna ve sağlığına vereceği zarar anlatılmaktadır. 'Impair' (bozmak, zayıflatmak, zarar vermek) bu olumsuz etkiyi ifade eder."
    },
    {
        "question_text": "The diplomat's highly ------- response to inquiries regarding the border dispute left international observers deeply skeptical of her government's true intentions.",
        "options": {"A": "straightforward", "B": "evasive", "C": "enthusiastic", "D": "detailed", "E": "sincere"},
        "correct_option": "B",
        "ai_explanation": "Uluslararası gözlemcilerin hükümetin niyetinden şüphe etmesi, verilen cevabın net olmadığını, konuyu saptırmaya yönelik olduğunu gösterir. 'Evasive' (kaçamak, kaçınan) doğru seçenektir."
    },
    {
        "question_text": "The extensive trans-continental railway network was constructed to ------- isolated commercial hubs that had been geographically separated for generations.",
        "options": {"A": "divide", "B": "connect", "C": "isolate", "D": "distinguish", "E": "compare"},
        "correct_option": "B",
        "ai_explanation": "Demiryolu ağının coğrafi olarak birbirinden ayrı kalmış ticari merkezleri bir araya getirme işlevi vurgulanmaktadır. 'Connect' (bağlamak, birleştirmek) doğru seçenektir."
    },
    {
        "question_text": "The playwright's latest theatrical production received ------- reviews from contemporary critics, who universally lauded its dramatic depth and stylistic originality.",
        "options": {"A": "mixed", "B": "scathing", "C": "mediocre", "D": "lukewarm", "E": "glowing"},
        "correct_option": "E",
        "ai_explanation": "Eleştirmenlerin eserin derinliğini ve özgünlüğünü tüm dünyada övmesi çok olumlu bir durumdur. 'Glowing' (coşkulu, çok olumlu, övgü dolu) bu durumla tutarlıdır."
    },
    {
        "question_text": "Climatologists are actively developing advanced mitigation strategies to ------- the adverse long-term impacts of global greenhouse gas accumulations.",
        "options": {"A": "intensify", "B": "counteract", "C": "overlook", "D": "celebrate", "E": "duplicate"},
        "correct_option": "B",
        "ai_explanation": "Bilim insanlarının amacı sera gazlarının olumsuz etkilerini nötrlemek ve bu etkilere karşı koymaktır. 'Counteract' (etkisini gidermek, karşı koymak) bu amaca tam uyar."
    },
    {
        "question_text": "The newly appointed director's remarkably ------- administrative philosophy encouraged researchers to collaborate across disciplines and undertake innovative risks.",
        "options": {"A": "authoritarian", "B": "rigid", "C": "inclusive", "D": "indifferent", "E": "distant"},
        "correct_option": "C",
        "ai_explanation": "Çalışanları fikir paylaşmaya ve disiplinler arası çalışmaya teşvik eden yönetim tarzı kapsayıcı olmalıdır. 'Inclusive' (kapsayıcı, kucaklayıcı) doğru seçenektir."
    },
    {
        "question_text": "The non-governmental organization's core mandate is to ------- the constitutional rights of marginalized populations through extensive legal advocacy.",
        "options": {"A": "undermine", "B": "uphold", "C": "suppress", "D": "ignore", "E": "question"},
        "correct_option": "B",
        "ai_explanation": "Sivil toplum kuruluşunun amacı azınlıkların ve dezavantajlı grupların anayasal haklarını savunmak ve korumaktır. 'Uphold' (savunmak, desteklemek, korumak) doğru seçenektir."
    },
    {
        "question_text": "The patient's remarkably rapid physiological ------- following the complex neurosurgical intervention astonished the entire medical board.",
        "options": {"A": "deterioration", "B": "recovery", "C": "withdrawal", "D": "confusion", "E": "isolation"},
        "correct_option": "B",
        "ai_explanation": "Ağır bir beyin ameliyatının ardından tıp heyetini şaşırtacak derecede olumlu giden durum hastanın iyileşme hızıdır. 'Recovery' (iyileşme, toparlanma) doğru seçenektir."
    },
    {
        "question_text": "The novelist's prose is celebrated for its ------- imagery, which effortlessly evokes a profound emotional response from the reader.",
        "options": {"A": "vague", "B": "sparse", "C": "vivid", "D": "dull", "E": "repetitive"},
        "correct_option": "C",
        "ai_explanation": "Okuyucuda derin bir duygusal karşılık uyandıran ve zihinde net resimler çizen tasvirler canlı ve etkilidir. 'Vivid' (canlı, parlak, net) doğru seçenektir."
    },
    {
        "question_text": "The United Nations attempted to ------- the two warring factions, but the deep-rooted ethnic animosity hindered any permanent peace agreement.",
        "options": {"A": "alienate", "B": "reconcile", "C": "provoke", "D": "separate", "E": "eliminate"},
        "correct_option": "B",
        "ai_explanation": "Derin düşmanlıkların barışı engellediği bir bağlamda, uluslararası kuruluşun amacı tarafları uzlaştırmaya çalışmaktır. 'Reconcile' (uzlaştırmak, barıştırmak) doğru seçenektir."
    },
    {
        "question_text": "Despite remaining an ------- settlement for centuries, the coastal town transformed into a bustling tourist hub after its inclusion in a historical documentary.",
        "options": {"A": "overcrowded", "B": "prosperous", "C": "obscure", "D": "accessible", "E": "celebrated"},
        "correct_option": "C",
        "ai_explanation": "'Despite' bağlacı zıtlık ister: Kasaba tanınmadan aniden popüler hale gelmiştir. 'Obscure' (tanınmamış) bu zıtlığa uyar."
    },
    {
        "question_text": "The international court declared that the blanket maritime treaty was ------- because crucial clauses had been signed under political coercion.",
        "options": {"A": "binding", "B": "void", "C": "valid", "D": "enforceable", "E": "transparent"},
        "correct_option": "B",
        "ai_explanation": "Baskı altında imzalanan bir sözleşme geçersizdir. 'Void' (geçersiz, hükümsüz) bu durumu ifade eder."
    },
    {
        "question_text": "The construction of the new highway will inevitably ------- the natural habitat of several protected species.",
        "options": {"A": "restore", "B": "disrupt", "C": "preserve", "D": "improve", "E": "expand"},
        "correct_option": "B",
        "ai_explanation": "Yeni bir otoyolun inşaatı doğal yaşam alanlarını olumsuz etkiler. 'Disrupt' (bozmak) bu olumsuz etkiyi ifade eder."
    },
    {
        "question_text": "The software update was intended to ------- the security vulnerabilities that hackers had been exploiting.",
        "options": {"A": "create", "B": "expose", "C": "patch", "D": "ignore", "E": "publicize"},
        "correct_option": "C",
        "ai_explanation": "Güvenlik açıklarını kapatmak için yazılım güncellemesi yapılır. 'Patch' (yamalamak) bu teknik bağlama uyar."
    },
    {
        "question_text": "The historical records were so ------- that researchers found it nearly impossible to piece together an accurate timeline.",
        "options": {"A": "detailed", "B": "comprehensive", "C": "fragmented", "D": "organized", "E": "accessible"},
        "correct_option": "C",
        "ai_explanation": "Doğru bir zaman çizelgesi oluşturmanın neredeyse imkânsız olması, kayıtların eksik/parçalı olduğunu gösterir. 'Fragmented' (parçalı) doğru seçenektir."
    },
    {
        "question_text": "The two countries signed a ------- agreement to cooperate on matters of border security and trade.",
        "options": {"A": "unilateral", "B": "bilateral", "C": "internal", "D": "confidential", "E": "temporary"},
        "correct_option": "B",
        "ai_explanation": "İki ülke arasında imzalanan bir anlaşma ikili bir nitelik taşır. 'Bilateral' (ikili, iki taraflı) EMBED doğru seçenektir."
    },
    {
        "question_text": "The philosopher's ideas were so ------- that they continue to influence thinkers even two centuries after his death.",
        "options": {"A": "irrelevant", "B": "outdated", "C": "profound", "D": "simplistic", "E": "contradictory"},
        "correct_option": "C",
        "ai_explanation": "İki yüzyıl sonra bile etkisini sürdüren fikirler derin ve kalıcı olmalıdır. 'Profound' (derin, köklü) doğru seçenektir."
    },
    {
        "question_text": "The company decided to ------- its operations in three new countries to increase its global market share.",
        "options": {"A": "reduce", "B": "suspend", "C": "expand", "D": "relocate", "E": "evaluate"},
        "correct_option": "C",
        "ai_explanation": "Üç yeni ülkeye açılmak, faaliyetlerin genişletildiğini gösterir. 'Expand' (genişletmek) doğru seçenektir."
    },
    {
        "question_text": "The documentary sought to ------- the myths surrounding the life of the controversial historical figure.",
        "options": {"A": "reinforce", "B": "debunk", "C": "create", "D": "celebrate", "E": "promote"},
        "correct_option": "B",
        "ai_explanation": "Tartışmalı bir tarihi figüre dair mitleri ele almak, onları çürütmek anlamına gelir. 'Debunk' (çürütmek) doğru seçenektir."
    },
    {
        "question_text": "The volunteers worked ------- to provide food and shelter for those affected by the devastating earthquake.",
        "options": {"A": "reluctantly", "B": "tirelessly", "C": "carelessly", "D": "occasionally", "E": "indifferently"},
        "correct_option": "B",
        "ai_explanation": "Yıkıcı bir depremden etkilenenlere yardım eden gönüllülerin yorulmadan çalıştığı anlaşılmaktadır. 'Tirelessly' (yorulmaksızın) doğru seçenektir."
    },
    {
        "question_text": "The young researcher's groundbreaking work in the field of genetics has ------- new possibilities for cancer treatment.",
        "options": {"A": "closed", "B": "ignored", "C": "limited", "D": "opened", "E": "questioned"},
        "correct_option": "D",
        "ai_explanation": "Öncü araştırmalar kanser tedavisinde yeni olanakların önünü açar. 'Opened' (açmak) bu bağlama uyar."
    },
    {
        "question_text": "The infrastructure proposal was ------- by the executive board after it became clear that it was not financially viable.",
        "options": {"A": "approved", "B": "celebrated", "C": "rejected", "D": "modified", "E": "funded"},
        "correct_option": "C",
        "ai_explanation": "Mali açıdan sürdürülebilir olmayan bir teklif reddedilir. 'Rejected' (reddedilmiş) doğru seçenektir."
    },
    {
        "question_text": "The journalist steadfastly refused to ------- her sources, even under intense pressure from the ruling authorities.",
        "options": {"A": "protect", "B": "reveal", "C": "contact", "D": "interview", "E": "appreciate"},
        "correct_option": "B",
        "ai_explanation": "Gazeteci baskı altında bile kaynağını açıklamamıştır; 'reveal' (açıklamak) doğru seçenektir. Cümle olumsuz anlamla kurulmuştur."
    },
    {
        "question_text": "The ------- nature of the sub-Saharan tribes, which required constant migration, eventually influenced their socio-economic structures.",
        "options": {"A": "sedentary", "B": "nomadic", "C": "predictable", "D": "rewarding", "E": "local"},
        "correct_option": "B",
        "ai_explanation": "Sürekli seyahat gerektiren bir iş göçebe/yerinde durmayan bir nitelik taşır. 'Nomadic' (göçebe) doğru seçenektir."
    },
    {
        "question_text": "The field archaeologists were genuinely delighted to ------- a well-preserved ancient settlement buried deep beneath the city.",
        "options": {"A": "bury", "B": "destroy", "C": "discover", "D": "overlook", "E": "abandon"},
        "correct_option": "C",
        "ai_explanation": "Arkeologların heyecan duyması, iyi korunmuş bir yerleşim yeri bulmalarından kaynaklanır. 'Discover' (keşfetmek) doğru seçenektir."
    },
    {
        "question_text": "The company's ------- approach to customer service and consumer fulfillment set it apart from its competitors in the retail industry.",
        "options": {"A": "indifferent", "B": "exemplary", "C": "inconsistent", "D": "minimal", "E": "delayed"},
        "correct_option": "B",
        "ai_explanation": "Rakiplerinden ayrışmasını sağlayan bir müşteri hizmeti anlayışı örnek nitelikte olmalıdır. 'Exemplary' (örnek) doğru seçenektir."
    },
    {
        "question_text": "The audit report revealed that the firm had been systematically ------- its financial records to intentionally mislead prospective investors.",
        "options": {"A": "auditing", "B": "falsifying", "C": "improving", "D": "simplifying", "E": "publishing"},
        "correct_option": "B",
        "ai_explanation": "Yatırımcıları yanıltmak amacıyla yapılan işlem, mali kayıtların tahrif edilmesidir. 'Falsifying' (tahrif etmek) doğru seçenektir."
    },
    {
        "question_text": "The two prominent scientists worked ------- on the research project, regularly reviewing each other's laboratory progress.",
        "options": {"A": "independently", "B": "reluctantly", "C": "collaboratively", "D": "competitively", "E": "secretly"},
        "correct_option": "C",
        "ai_explanation": "Veri paylaşımı ve birbirlerinin ilerlemesini takip etmek iş birliğini gösterir. 'Collaboratively' (iş birliği içinde) doğru seçenektir."
    },
    {
        "question_text": "The metropolitan city council voted to ------- the historic district in order to firmly protect its architectural heritage.",
        "options": {"A": "demolish", "B": "commercialize", "C": "preserve", "D": "expand", "E": "relocate"},
        "correct_option": "C",
        "ai_explanation": "Mimari mirası koruma amacı, tarihi bölgenin muhafaza edilmesini gerektirir. 'Preserve' (korumak) doğru seçenektir."
    },
    {
        "question_text": "The groundbreaking scientific study completely ------- previous assumptions about the direct relationship between diet and mental health.",
        "options": {"A": "confirmed", "B": "challenged", "C": "ignored", "D": "repeated", "E": "simplified"},
        "correct_option": "B",
        "ai_explanation": "Yeni bir araştırmanın önceki varsayımlara yaklaşımı genellikle onları sorgulamak yönünde olur. 'Challenged' (sorgulamak) doğru seçenektir."
    },
    {
        "question_text": "The biology student's ------- curiosity about the natural world eventually led him to pursue a career in academic research.",
        "options": {"A": "fading", "B": "limited", "C": "insatiable", "D": "occasional", "E": "superficial"},
        "correct_option": "C",
        "ai_explanation": "Doğal dünyaya duyulan merakın biyoloji kariyerine yol açması, bu merakın doyumsuz/sınırsız olduğunu gösterir. 'Insatiable' (doyumsuz) doğru seçenektir."
    },
    {
        "question_text": "The department manager's chronic tendency to ------- crucial organizational decisions often caused immense frustration among team members.",
        "options": {"A": "rush", "B": "delegate", "C": "postpone", "D": "announce", "E": "document"},
        "correct_option": "C",
        "ai_explanation": "Önemli kararların sürekli ertelenmesi ekip üyebilirinde hayal kırıklığı yaratır. 'Postpone' (ertelemek) doğru seçenektir."
    },
    {
        "question_text": "The vocal opposition party called for an immediate, ------- inquiry into the government's highly controversial handling of public funds.",
        "options": {"A": "internal", "B": "independent", "C": "informal", "D": "incomplete", "E": "occasional"},
        "correct_option": "B",
        "ai_explanation": "Muhalefet partisi, kamu fonlarının kullanımını araştırmak için bağımsız bir soruşturma istemiştir. 'Independent' (bağımsız) doğru seçenektir."
    },
    {
        "question_text": "The local community came together to ------- a magnificent memorial in honor of those who tragically lost their lives in the disaster.",
        "options": {"A": "demolish", "B": "ignore", "C": "erect", "D": "relocate", "E": "question"},
        "correct_option": "C",
        "ai_explanation": "Hayatını kaybedenleri anmak için topluluk bir anıt dikmiştir. 'Erect' (dikmek, inşa etmek) doğru seçenektir."
    },
    {
        "question_text": "After nearly three consecutive years of ------- negotiations, the two tech companies finally agreed on the formal terms of the merger.",
        "options": {"A": "brief", "B": "productive", "C": "effortless", "D": "prolonged", "E": "unnecessary"},
        "correct_option": "D",
        "ai_explanation": "'After years of' ifadesi uzun süren bir süreci işaret eder. 'Prolonged' (uzun süren) bu zaman vurgusuna uygundur."
    },
    {
        "question_text": "The prime minister's highly ------- choice of words during the emergency session prevented the volatile situation from escalating further.",
        "options": {"A": "careless", "B": "provocative", "C": "tactful", "D": "ambiguous", "E": "aggressive"},
        "correct_option": "C",
        "ai_explanation": "Diplomatik bir krizi önleyen kelime seçimi incelikli/diplomatik olmalıdır. 'Tactful' (nazik, incelikli) doğru seçenektir."
    },
    {
        "question_text": "The children were completely ------- by the veteran magician's intricate performance and kept eagerly asking for more tricks.",
        "options": {"A": "bored", "B": "frightened", "C": "captivated", "D": "confused", "E": "disappointed"},
        "correct_option": "C",
        "ai_explanation": "Gösteriden sonra daha fazla numara istemeleri çocukların büyülendiğini gösterir. 'Captivated' (büyülenmiş) doğru seçenektir."
    },
    {
        "question_text": "The results of the laboratory experiment were highly ------- and could not be adequately explained by any existing scientific theory.",
        "options": {"A": "predictable", "B": "expected", "C": "anomalous", "D": "consistent", "E": "straightforward"},
        "correct_option": "C",
        "ai_explanation": "Mevcut hiçbir bilimsel teoriyle açıklanamayan sonuçlar anormal/sapkın sonuçlardır. 'Anomalous' (anormal) doğru seçenektir."
    },
    {
        "question_text": "The non-profit foundation was established with the sole ------- of providing academic scholarships to students from low-income background.",
        "options": {"A": "condition", "B": "purpose", "C": "result", "D": "requirement", "E": "benefit"},
        "correct_option": "B",
        "ai_explanation": "Vakfın kurulmasının arkasındaki tek neden burs sağlamaktır. 'Purpose' (amaç) doğru seçenektir."
    },
    {
        "question_text": "The historic treaty was signed primarily as a ------- measure to prevent future military conflicts between the neighboring nations.",
        "options": {"A": "retaliatory", "B": "provocative", "C": "preventive", "D": "symbolic", "E": "temporary"},
        "correct_option": "C",
        "ai_explanation": "Daha fazla çatışmayı önlemek amacıyla imzalanan antlaşma önleyici bir nitelik taşır. 'Preventive' (önleyici) doğru seçenektir."
    },
    {
        "question_text": "The leading scientist's ------- approach to data collection, in which she questioned every single assumption, led to several breakthroughs.",
        "options": {"A": "conventional", "B": "rigorous", "C": "careless", "D": "superficial", "E": "rushed"},
        "correct_option": "B",
        "ai_explanation": "Her varsayımı sorgulayan ve çığır açan keşiflere yol açan bir araştırma anlayışı titiz olmalıdır. 'Rigorous' (titiz, sıkı) doğru seçenektir."
    },
    {
        "question_text": "The unexpected, severe drought has had a ------- impact on the local agricultural sector, directly threatening regional food security.",
        "options": {"A": "minimal", "B": "positive", "C": "negligible", "D": "devastating", "E": "temporary"},
        "correct_option": "D",
        "ai_explanation": "Gıda güvenliğini tehdit eden şiddetli bir kuraklık tarım sektörünü yıkıcı biçimde etkiler. 'Devastating' (yıkıcı) doğru seçenektir."
    },
    {
        "question_text": "The political student's analytical essay was widely praised for its ------- argument and exceptionally well-structured paragraphs.",
        "options": {"A": "incoherent", "B": "coherent", "C": "repetitive", "D": "incomplete", "E": "biased"},
        "correct_option": "B",
        "ai_explanation": "Övgü alan ve iyi yapılandırılmış bir deneme tutarlı/mantıklı bir argüman içerir. 'Coherent' (tutarlı) doğru seçenektir."
    },
    {
        "question_text": "The conservative board members remained highly ------- about the merger, insisting that more financial forecasting was mandatory.",
        "options": {"A": "enthusiastic", "B": "committed", "C": "skeptical", "D": "confident", "E": "satisfied"},
        "correct_option": "C",
        "ai_explanation": "Daha fazla veri talep etmek ve kararsız kalmak, yöneticilerin kuşkuyla yaklaştığını gösterir. 'Skeptical' (şüpheci) doğru seçenektir."
    },
    {
        "question_text": "The newly ratified law was specifically designed to ------- the commercial activities of factories that had been polluting the area.",
        "options": {"A": "encourage", "B": "regulate", "C": "ignore", "D": "fund", "E": "expand"},
        "correct_option": "B",
        "ai_explanation": "Yıllardır nehri kirleten şirketlerin faaliyetlerini kontrol altına almak için yeni bir yasa çıkarılmıştır. 'Regulate' (düzenlemek) doğru seçenektir."
    },
    {
        "question_text": "The elderly patient was strictly advised to ------- any strenuous physical activity for at least two months following the major surgery.",
        "options": {"A": "continue", "B": "pursue", "C": "avoid", "D": "monitor", "E": "increase"},
        "correct_option": "C",
        "ai_explanation": "Ameliyat sonrasında doktorlar genellikle ağır fiziksel aktiviteden uzak durulmasını önerir. 'Avoid' (kaçınmak) doğru seçenektir."
    },
    {
        "question_text": "Despite her incredibly ------- and demanding schedule, the CEO always allocated time to communicate with international stakeholders.",
        "options": {"A": "flexible", "B": "empty", "C": "hectic", "D": "predictable", "E": "manageable"},
        "correct_option": "C",
        "ai_explanation": "'Despite' zıtlık kurar: yoğun programa rağmen CEO çalışanlarla vakit ayırabilmiştir. 'Hectic' (çok yoğun) bu zıtlığa uyar."
    },
    {
        "question_text": "The newly released documentary provided a highly ------- account of the sociological events leading up to the historic collapse.",
        "options": {"A": "biased", "B": "superficial", "C": "comprehensive", "D": "inaccurate", "E": "exaggerated"},
        "correct_option": "C",
        "ai_explanation": "2008 mali krizine giden süreci anlatan nitelikli bir belgesel kapsamlı bir anlatım sunar. 'Comprehensive' (kapsamlı) doğru seçenektir."
    },
    {
        "question_text": "The structural layout of the new international airport terminal was built to ------- up to 60 million passengers annually.",
        "options": {"A": "restrict", "B": "accommodate", "C": "discourage", "D": "replace", "E": "reduce"},
        "correct_option": "B",
        "ai_explanation": "Terminalin yıllık 50 milyon yolcuya hizmet edecek şekilde tasarlanması kapasiteyi gündeme getirir. 'Accommodate' (ağırlamak) doğru seçenektir."
    },
    {
        "question_text": "The clinical psychiatrist's calm and ------- tone immediately put the anxious crowd at ease during the speech.",
        "options": {"A": "aggressive", "B": "condescending", "C": "reassuring", "D": "monotonous", "E": "intimidating"},
        "correct_option": "C",
        "ai_explanation": "İzleyiciyi rahatlatıp soru sormalarını sağlayan bir ses tonu güven verici olmalıdır. 'Reassuring' (güven verici) doğru seçenektir."
    },
    {
        "question_text": "The geology professor urged his students to ------- data from cross-cultural studies rather than depending on local findings.",
        "options": {"A": "gather", "B": "ignore", "C": "memorize", "D": "reject", "E": "limit"},
        "correct_option": "A",
        "ai_explanation": "Tek bir kaynakla yetinmeden bilgi toplamak önerilmektedir. 'Gather' (toplamak) doğru seçenektir."
    },
    {
        "question_text": "The research laboratory's ------- findings completely contradicted decades of firmly established academic consensus on the disease.",
        "options": {"A": "expected", "B": "preliminary", "C": "controversial", "D": "outdated", "E": "irrelevant"},
        "correct_option": "C",
        "ai_explanation": "Onlarca yıllık bilimsel uzlaşıyı çürüten bulgular tartışmalı/polemik yaratan nitelikte olmalıdır. 'Controversial' (tartışmalı) doğru seçenektir."
    },
    {
        "question_text": "The newly introduced medical treatment proved remarkably ------- in alleviating respiratory symptoms in the vast majority of trial patients.",
        "options": {"A": "harmful", "B": "ineffective", "C": "effective", "D": "experimental", "E": "unnecessary"},
        "correct_option": "C",
        "ai_explanation": "Hastaların yüzde doksanından fazlasında belirtileri azaltmak, tedavinin etkili olduğunu gösterir. 'Effective' (etkili) doğru seçenektir."
    },
    {
        "question_text": "The software vendor's complete ------- to deliver the project on schedule severely damaged its professional standing with corporate clients.",
        "options": {"A": "ability", "B": "commitment", "C": "failure", "D": "success", "E": "determination"},
        "correct_option": "C",
        "ai_explanation": "Müşteriyle ilişkiyi zedeleyen durum, projenin zamanında teslim edilememesidir. 'Failure' (başarısızlık) doğru seçenektir."
    },
    {
        "question_text": "Her completely ------- attitude during the strategic project meeting made it clear that she was no longer interested in the task.",
        "options": {"A": "enthusiastic", "B": "diligent", "C": "passionate", "D": "apathetic", "E": "attentive"},
        "correct_option": "D",
        "ai_explanation": "Projeye tam olarak bağlı olmadığını ortaya koyan davranış ilgisizlik/umursamazlık göstergesidir. 'Apathetic' (ilgisiz, umursamaz) doğru seçenektir."
    },
    {
        "question_text": "The national healthcare agency launched an extensive campaign to ------- public awareness about the chronic perils of high sugar intake.",
        "options": {"A": "reduce", "B": "ignore", "C": "raise", "D": "limit", "E": "question"},
        "correct_option": "C",
        "ai_explanation": "Tehlikeler hakkında kamuoyunu bilgilendirmek için farkındalığın artırılması gerekir. 'Raise' (artırmak, yükseltmek) doğru seçenektir."
    },
    {
        "question_text": "The marketing firm's new advertisement campaign was specifically curated to ------- to a younger demographic across the country.",
        "options": {"A": "appeal", "B": "object", "C": "refer", "D": "apply", "E": "conform"},
        "correct_option": "A",
        "ai_explanation": "Daha önce göz ardı edilen genç bir kitleye yönelik ürün hattı, o kitleye hitap etmek için tasarlanmıştır. 'Appeal to' (hitap etmek, çekici gelmek) doğru seçenektir."
    },
    {
        "question_text": "The academic historian's new publication was universally praised for its ------- archival research and its literary narrative.",
        "options": {"A": "superficial", "B": "biased", "C": "meticulous", "D": "hurried", "E": "incomplete"},
        "correct_option": "C",
        "ai_explanation": "Unutulmuş bir dönemi canlandıran ve övgü alan tarih kitabının araştırması titiz/ayrıntılı olmalıdır. 'Meticulous' (titiz, özenli) doğru seçenektir."
    },
    {
        "question_text": "Following intense mediation, the two nations finally reached a ------- agreement that, although flawed, brought an end to the war.",
        "options": {"A": "definitive", "B": "comprehensive", "C": "compromise", "D": "unilateral", "E": "binding"},
        "correct_option": "C",
        "ai_explanation": "Mükemmel olmasa da her iki tarafın kabul ettiği bir anlaşma uzlaşmayı temsil eder. 'Compromise' (uzlaşma, taviz verme) doğru seçenektir."
    },
    {
        "question_text": "The prime minister's highly ------- remarks regarding the opposition faction sparked an incredibly heated debate in the parliament.",
        "options": {"A": "conciliatory", "B": "inflammatory", "C": "diplomatic", "D": "cautious", "E": "ambiguous"},
        "correct_option": "B",
        "ai_explanation": "Parlamentoda sert bir tartışma başlatan açıklamalar kışkırtıcı/ateşleyici nitelikte olmalıdır. 'Inflammatory' (kışkırtıcı) doğru seçenektir."
    },
    {
        "question_text": "The vocal environmental collective vehemently ------- the government's strategic plan to construct a massive coal-fired plant.",
        "options": {"A": "supported", "B": "funded", "C": "opposed", "D": "designed", "E": "welcomed"},
        "correct_option": "C",
        "ai_explanation": "Çevre grubu, yeni bir kömür santralinin inşasına karşı çıkmıştır. 'Opposed' (karşı çıkmak) doğru seçenektir."
    },
    {
        "question_text": "The most defining ------- between the two psychological theories lies in their fundamentally unique views on human nature.",
        "options": {"A": "similarity", "B": "connection", "C": "distinction", "D": "overlap", "E": "relationship"},
        "correct_option": "C",
        "ai_explanation": "İki teori arasındaki temelden farklı varsayımlar, aralarındaki ayrımı/farkı ortaya koyar. 'Distinction' (ayrım, fark) doğru seçenektir."
    },
    {
        "question_text": "The remote mountain village had remained completely ------- for decades until a modern highway network was constructed.",
        "options": {"A": "connected", "B": "isolated", "C": "developed", "D": "populated", "E": "accessible"},
        "correct_option": "B",
        "ai_explanation": "Yeni bir yol yapılana kadar ülkenin geri kalanından kopuk olan köy izole/tecrit edilmiş durumdaydı. 'Isolated' (izole edilmiş) doğru seçenektir."
    },
    {
        "question_text": "The chief surgeon's ------- clinical skill and calm demeanor during the complicated medical operation reassured the entire staff.",
        "options": {"A": "amateur", "B": "questionable", "C": "exceptional", "D": "average", "E": "developing"},
        "correct_option": "C",
        "ai_explanation": "Karmaşık bir operasyonda hem hastayı hem de ekibi rahatlatan bir cerrah olağanüstü yeteneklere sahip olmalıdır. 'Exceptional' (olağanüstü) doğru seçenektir."
    },
    {
        "question_text": "The automotive manufacturer's chronic ------- to adapt to changing global environmental regulations led to its ultimate financial ruin.",
        "options": {"A": "ability", "B": "willingness", "C": "failure", "D": "commitment", "E": "strategy"},
        "correct_option": "C",
        "ai_explanation": "Değişen pazar koşullarına uyum sağlayamamak şirketin çöküşüne yol açmıştır. 'Failure' (başarısızlık, yetersizlik) doğru seçenektir."
    },
    {
        "question_text": "The university mentor's highly ------- feedback helped the graduate students understand exactly how to refine their theses.",
        "options": {"A": "vague", "B": "discouraging", "C": "constructive", "D": "delayed", "E": "irrelevant"},
        "correct_option": "C",
        "ai_explanation": "Öğrencilerin tam olarak neyi geliştirmeleri gerektiğini anlamalarına yardımcı olan geri bildirim yapıcı nitelikte olmalıdır. 'Constructive' (yapıcı) doğru seçenektir."
    },
    {
        "question_text": "The municipal administration's new urban infrastructure policy was heavily ------- by global human rights watchdogs.",
        "options": {"A": "praised", "B": "welcomed", "C": "endorsed", "D": "condemned", "E": "celebrated"},
        "correct_option": "D",
        "ai_explanation": "İfaded özgürlüğünü kısıtlama potansiyeli taşıyan bir politika insan hakları örgütleri tarafından kınanır. 'Condemned' (kınamak) doğru seçenektir."
    },
    {
        "question_text": "The overall clinical ------- of the newly synthesized vaccine was fully confirmed through a series of multi-phase medical trials.",
        "options": {"A": "failure", "B": "cost", "C": "efficacy", "D": "availability", "E": "complexity"},
        "correct_option": "C",
        "ai_explanation": "Klinik denemelerle doğrulanan şey aşının virüse karşı etkinliği/başarısıdır. 'Efficacy' (etkinlik, verimlilik) doğru seçenektir."
    },
    {
        "question_text": "The local state government decided to completely ------- the use of single-use plastics to tackle rising maritime pollution.",
        "options": {"A": "encourage", "B": "subsidize", "C": "ban", "D": "promote", "E": "ignore"},
        "correct_option": "C",
        "ai_explanation": "Çevre kirliliğini azaltmak için tek kullanımlık plastiklerin kullanımının yasaklanması en uygun önlemdir. 'Ban' (yasaklamak) doğru seçenektir."
    },
    {
        "question_text": "The core findings of the public investigation were entirely ------- with the statistical evidence collected previously.",
        "options": {"A": "inconsistent", "B": "contradictory", "C": "consistent", "D": "unrelated", "E": "incompatible"},
        "correct_option": "C",
        "ai_explanation": "Davayı güçlendiren bulgular, görgü tanıklarının ifadeleriyle örtüşmelidir. 'Consistent' (tutarlı, örtüşen) doğru seçenektir."
    },
    {
        "question_text": "The world-renowned modernist architect's blueprint for the national gallery was both ------- and highly functional.",
        "options": {"A": "ordinary", "B": "costly", "C": "outdated", "D": "innovative", "E": "controversial"},
        "correct_option": "D",
        "ai_explanation": "Tüm dünyada eleştirmenleri etkileyen hem işlevsel hem de özgün bir tasarım yenilikçi olmalıdır. 'Innovative' (yenilikçi) doğru seçenektir."
    },
    {
        "question_text": "The senior regional manager warmly ------- the sales team for their exceptional performance during the past quarter.",
        "options": {"A": "criticized", "B": "ignored", "C": "commended", "D": "dismissed", "E": "questioned"},
        "correct_option": "C",
        "ai_explanation": "Olağanüstü performans için yeni çalışanın takdir edilmesi/övülmesi beklenir. 'Commended' (takdir etmek, övmek) doğru seçenektir."
    },
    {
        "question_text": "The global charity organization's annual review confirmed that its programs had radically ------- the lives of refugees.",
        "options": {"A": "worsened", "B": "complicated", "C": "transformed", "D": "ignored", "E": "limited"},
        "correct_option": "C",
        "ai_explanation": "Binlerce ihtiyaç sahibinin hayatına dokunan programlar o hayatları köklü biçimde değiştirmiştir. 'Transformed' (dönüştürmek) doğru seçenektir."
    },
    {
        "question_text": "The senior diplomat's highly ------- remarks were unfortunately taken out of context and heavily misrepresented by the media.",
        "options": {"A": "deliberate", "B": "offhand", "C": "formal", "D": "prepared", "E": "scripted"},
        "correct_option": "B",
        "ai_explanation": "Bağlamdan koparılıp çarpıtılan açıklamalar, hazırlıksız/gelişigüzel yapılan yorumlar olmalıdır. 'Offhand' (düşünmeden, gelişigüzel) doğru seçenektir."
    },
    {
        "question_text": "The regional financial crisis forced thousands of highly skilled laborers to ------- abroad in pursuit of better career prospects.",
        "options": {"A": "remain", "B": "migrate", "C": "retire", "D": "invest", "E": "settle"},
        "correct_option": "B",
        "ai_explanation": "Ekonomik kriz, nitelikli işçileri daha iyi iş imkânları için yurt dışına göç etmeye yöneltmiştir. 'Migrate' (göç etmek) doğru seçenektir."
    },
    {
        "question_text": "The newly uncovered historical architecture was so ------- that research historians spent decades trying to classify its origin.",
        "options": {"A": "familiar", "B": "well-documented", "C": "modern", "D": "enigmatic", "E": "accessible"},
        "correct_option": "D",
        "ai_explanation": "Hangi medeniyete ait olduğu yıllarca araştırılan kalıntılar gizemli/bulmaca niteliğindedir. 'Enigmatic' (gizemli, esrarengiz) doğru seçenektir."
    },
    {
        "question_text": "The intensive vocational framework was structurally engineered to ------- recent graduates with the skills required by the market.",
        "options": {"A": "deprive", "B": "equip", "C": "distract", "D": "discourage", "E": "burden"},
        "correct_option": "B",
        "ai_explanation": "Çalışanların dijital ekonomi için gereken becerilerle donatılması, eğitim programının amacıdır. 'Equip' (donatmak) doğru seçenektir."
    },
    {
        "question_text": "The general public was completely ------- when the official inquiry revealed that the board had known about the dynamic hazards.",
        "options": {"A": "indifferent", "B": "unsurprised", "C": "outraged", "D": "relieved", "E": "amused"},
        "correct_option": "C",
        "ai_explanation": "Yetkililerin tehlikeyi yıllarca gizlediğinin ortaya çıkması halkta öfke yaratmıştır. 'Outraged' (öfkeli, kızmış) doğru seçenektir."
    },
    {
        "question_text": "The constitutional judicial reform was long ------- by civic experts who had been pointing out legal systemic flaws for years.",
        "options": {"A": "opposed", "B": "criticized", "C": "overdue", "D": "unexpected", "E": "celebrated"},
        "correct_option": "C",
        "ai_explanation": "Yıllardır uyarı yapan uzmanlar için bu reform çok geç yapılmış/gecikmiş bir adımdır. 'Overdue' (gecikmiş, çoktan yapılması gereken) doğru seçenektir."
    },
    {
        "question_text": "The pharmaceutical tech company's ------- commercial expansion over the past decade secured its position as a global leader.",
        "options": {"A": "sluggish", "B": "inconsistent", "C": "stagnant", "D": "exponential", "E": "minimal"},
        "correct_option": "D",
        "ai_explanation": "On yıl içinde dünyanın en değerli markalarından biri olmak üssel/hızla katlanarak artan bir büyümeyi gerektirir. 'Exponential' (üssel, katlanarak artan) doğru seçenektir."
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    for q in SEED_QUESTIONS:
        if not question_exists(q["question_text"]):
            save_ai_question(
                category="vocabulary",
                question_text=q["question_text"],
                options=q["options"],
                correct_option=q["correct_option"],
                ai_explanation=q["ai_explanation"],
            )
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/api/register", response_model=TokenResponse)
def register(payload: UserRegister):
    email = payload.email.strip().lower()
    if "@" not in email or len(payload.password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Geçerli bir email ve en az 6 karakterli bir şifre girmelisin.",
        )

    user_id = create_user(email, hash_password(payload.password))
    if user_id is None:
        raise HTTPException(status_code=400, detail="Bu email zaten kayıtlı.")

    token = create_token(user_id)
    return TokenResponse(
        access_token=token,
        user=UserOut(id=user_id, email=email, solved_count=0, correct_count=0),
    )


@app.post("/api/login", response_model=TokenResponse)
def login(payload: UserLogin):
    email = payload.email.strip().lower()
    row = get_user_by_email(email)
    if not row or not verify_password(payload.password, row[2]):
        raise HTTPException(status_code=401, detail="Email veya şifre hatalı.")

    user_id, user_email, _hash, solved_count, correct_count = row
    token = create_token(user_id)
    return TokenResponse(
        access_token=token,
        user=UserOut(id=user_id, email=user_email, solved_count=solved_count, correct_count=correct_count),
    )


@app.get("/api/me", response_model=UserOut)
def get_me(user_id: int = Depends(get_current_user_id)):
    row = get_user_by_id(user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
    uid, email, _hash, solved_count, correct_count = row
    return UserOut(id=uid, email=email, solved_count=solved_count, correct_count=correct_count)


@app.post("/api/answer", response_model=UserOut)
def answer_question(payload: AnswerSubmission, user_id: int = Depends(get_current_user_id)):
    """
    Frontend cevabın doğru olup olmadığını zaten bildiği için (soru içinde
    correct_option var), is_correct bilgisini de bu endpoint'e gönderir.
    İstatistik veritabanında, kullanıcıya özel olarak güncellenir.
    """
    row = get_question_by_id(payload.question_id)
    correct_option = row[3] if row else None

    is_correct = (correct_option is not None) and (payload.selected_option == correct_option)
    update_user_stats(user_id, is_correct)

    urow = get_user_by_id(user_id)
    uid, email, _hash, solved_count, correct_count = urow
    return UserOut(id=uid, email=email, solved_count=solved_count, correct_count=correct_count)



@app.get("/api/next-question")
def next_question():
    category = "vocabulary"
    count = get_question_count(category)

    if count == 0:
        return {"error": "loading"}

    row = get_random_stored_question(category)
    if not row:
        return {"error": "loading"}

    return {
        "id": row[0],
        "question_text": row[1],
        "options": json.loads(row[2]),
        "correct_option": row[3],
        "ai_explanation": row[4],
        "current_count": count,
    }


@app.post("/api/add-question")
def add_question(payload: AIQuestionFormat):
    """
    Yeni bir soruyu depoya ekler. Bu endpoint, soruları otomatik üreten
    bir dış servis (örn. bir LLM'e istek atan bir script) tarafından
    çagrılmak üzere tasarlanmıştır; ai_explanation alanını da
    payload'a eklemen gerekirse modeli genişletebilirsin.
    """
    if payload.correct_option not in payload.options:
        raise HTTPException(status_code=400, detail="correct_option, options içinde bulunmalı.")

    save_ai_question(
        category=payload.category,
        question_text=payload.question_text,
        options=payload.options,
        correct_option=payload.correct_option,
        ai_explanation="",
    )
    return {"status": "ok", "current_count": get_question_count(payload.category)}


@app.get("/", response_class=HTMLResponse)
def read_index():
    if not INDEX_FILE.exists():
        return HTMLResponse(
            "🌀 Hata: 'index.html' dosyası bulunamadı! "
            "Lütfen main.py ile aynı klasörde oldugundan emin ol.",
            status_code=500,
        )
    return INDEX_FILE.read_text(encoding="utf-8")
