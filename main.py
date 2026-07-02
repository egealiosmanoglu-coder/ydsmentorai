import os
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

import google.generativeai as genai

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
    verify_user_email,
    update_user_password,
    create_email_token,
    use_email_token,
    get_all_users,
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
    AskMentorRequest,
)
from auth import hash_password, verify_password, create_token, get_current_user_id
from email_service import send_verification_email, send_password_reset_email

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"

# Çevresel Değişkenler
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "degistir-bunu")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Gemini API Yapılandırması
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


SEED_QUESTIONS = [
    {
        "question_text": "The government decided to ------- the old building because it was no longer safe for public use.",
        "options": {"A": "demolish", "B": "construct", "C": "renovate", "D": "preserve", "E": "abandon"},
        "correct_option": "A",
        "ai_explanation": "Cümlede binanın artık güvenli olmadığı (no longer safe) belirtilerek yıkılması kararı vurgulanmıştır. 'Demolish' (yıkmak, yerle bir etmek) kelimesi bağlama tam uymaktadır.",
    },
    {
        "question_text": "Despite the heavy criticism, the committee remained ------- in its decision to approve the new policy.",
        "options": {"A": "hesitant", "B": "resolute", "C": "ambiguous", "D": "indifferent", "E": "reluctant"},
        "correct_option": "B",
        "ai_explanation": "'Despite' kelimesi bir zıtlık kurar: eleştirilere rağmen komite kararından vazgeçmemiştir. 'Resolute' (kararlı, azimli) bu zıtlığa en uygun anlamı verir.",
    },
    {
        "question_text": "The scientist's findings were so ------- that even her harshest critics had to acknowledge their validity.",
        "options": {"A": "trivial", "B": "compelling", "C": "questionable", "D": "obscure", "E": "premature"},
        "correct_option": "B",
        "ai_explanation": "Cümlede en sert eleştirmenlerin bile bulguların geçerliliğini kabul etmek zorunda kaldığı belirtiliyor; bu da bulguların ikna edici/güçlü olduğunu gösterir. 'Compelling' (ikna edici, etkileyici) doğru seçenektir.",
    },
    {
        "question_text": "The negotiations were ------- by both parties' refusal to make even the smallest compromise.",
        "options": {"A": "facilitated", "B": "hindered", "C": "accelerated", "D": "celebrated", "E": "simplified"},
        "correct_option": "B",
        "ai_explanation": "Her iki tarafın da küçük bir tavizden bile kaçınması müzakerelerin önünü tıkamıştır. 'Hindered' (engellenmiş, aksamış) bu olumsuz etkiyi karşılar.",
    },
    {
        "question_text": "Although the evidence was largely -------, the jury still found it convincing enough to reach a verdict.",
        "options": {"A": "circumstantial", "B": "conclusive", "C": "irrelevant", "D": "fabricated", "E": "redundant"},
        "correct_option": "A",
        "ai_explanation": "'Although' zıtlık kurar: kanıt dolaylı/kesin olmamasına rağmen jüri yine de ikna olmuştur. 'Circumstantial' (dolaylı, ipuçlarına dayanan) bu zıtlığa uyar.",
    },
    {
        "question_text": "The company's profits have shown a ------- decline over the past three quarters, raising concerns among investors.",
        "options": {"A": "negligible", "B": "marginal", "C": "steady", "D": "momentary", "E": "reversible"},
        "correct_option": "C",
        "ai_explanation": "Üç çeyrek boyunca süren ve yatırımcıları endişelendiren bir düşüş, ani değil sürekli/istikrarlı bir gerilemeyi işaret eder. 'Steady' (istikrarlı, sürekli) doğru seçenektir.",
    },
    {
        "question_text": "Her ------- to detail made her the perfect candidate for the meticulous research position.",
        "options": {"A": "indifference", "B": "attention", "C": "aversion", "D": "resistance", "E": "neglect"},
        "correct_option": "B",
        "ai_explanation": "Titiz bir araştırma pozisyonu için ideal aday olmasının sebebi detaylara verdiği önemdir. 'Attention to detail' (detaylara dikkat) kalıbı bağlama uyar.",
    },
    {
        "question_text": "The new regulations are intended to ------- pollution levels in urban areas over the next decade.",
        "options": {"A": "exacerbate", "B": "mitigate", "C": "ignore", "D": "publicize", "E": "complicate"},
        "correct_option": "B",
        "ai_explanation": "Yeni düzenlemelerin amacı kirliliği azaltmaktır. 'Mitigate' (hafifletmek, azaltmak) bu olumlu amaca uygun düşer.",
    },
    {
        "question_text": "The professor's lecture was so ------- that several students struggled to follow the main argument.",
        "options": {"A": "lucid", "B": "convoluted", "C": "concise", "D": "engaging", "E": "rehearsed"},
        "correct_option": "B",
        "ai_explanation": "Öğrencilerin ana fikri takip etmekte zorlanması dersin karmaşık/dolambaçlı olduğunu gösterir. 'Convoluted' (karmaşık, dolambaçlı) doğru seçenektir.",
    },
    {
        "question_text": "The CEO's decision to cut costs was met with ------- from employees who feared layoffs.",
        "options": {"A": "enthusiasm", "B": "apathy", "C": "resistance", "D": "approval", "E": "gratitude"},
        "correct_option": "C",
        "ai_explanation": "İşten çıkarılma korkusu yaşayan çalışanların tepkisi olumsuz olacaktır. 'Resistance' (direniş, karşı çıkma) bu korkuyla tutarlıdır.",
    },
    {
        "question_text": "The ancient manuscript was so ------- that historians had to use special equipment just to handle it.",
        "options": {"A": "durable", "B": "fragile", "C": "ordinary", "D": "replicated", "E": "abundant"},
        "correct_option": "B",
        "ai_explanation": "Özel ekipman gerektirecek kadar hassas olması, belgenin kırılgan/dayanıksız olduğunu gösterir. 'Fragile' (kırılgan) doğru seçenektir.",
    },
    {
        "question_text": "The witness's account was ------- with the physical evidence found at the scene, casting doubt on her testimony.",
        "options": {"A": "consistent", "B": "compatible", "C": "inconsistent", "D": "aligned", "E": "synchronized"},
        "correct_option": "C",
        "ai_explanation": "Tanığın ifadesinin şüphe uyandırması, fiziksel kanıtlarla çelişmesinden kaynaklanır. 'Inconsistent' (tutarsız, çelişen) bu durumu doğru ifade eder.",
    },
    {
        "question_text": "The startup's rapid growth can be attributed to its ------- approach to solving everyday problems.",
        "options": {"A": "conventional", "B": "innovative", "C": "outdated", "D": "indecisive", "E": "passive"},
        "correct_option": "B",
        "ai_explanation": "Hızlı büyümenin sebebi günlük sorunlara getirdiği yenilikçi çözümlerdir. 'Innovative' (yenilikçi) bağlama en uygun kelimedir.",
    },
    {
        "question_text": "The politician was accused of being ------- after changing his stance on the issue multiple times within a single year.",
        "options": {"A": "consistent", "B": "principled", "C": "opportunistic", "D": "transparent", "E": "diplomatic"},
        "correct_option": "C",
        "ai_explanation": "Bir yıl içinde tutumunu defalarca değiştirmesi, ilkesizce fırsatçı davrandığı izlenimini verir. 'Opportunistic' (fırsatçı) doğru seçenektir.",
    },
    {
        "question_text": "The medication had a ------- effect on the patient, causing drowsiness that lasted for several hours.",
        "options": {"A": "negligible", "B": "pronounced", "C": "delayed", "D": "reversible", "E": "imaginary"},
        "correct_option": "B",
        "ai_explanation": "Saatlerce süren bir uyuşukluk, ilacın belirgin/güçlü bir etkisi olduğunu gösterir. 'Pronounced' (belirgin, güçlü) bağlama uyar.",
    },
    {
        "question_text": "The museum's new exhibit aims to ------- visitors about the often-overlooked history of the region.",
        "options": {"A": "entertain", "B": "enlighten", "C": "confuse", "D": "discourage", "E": "distract"},
        "correct_option": "B",
        "ai_explanation": "Sergi, genelde göz ardı edilen bir tarihi ziyaretçilere öğretmeyi/aydınlatmayı amaçlıyor. 'Enlighten' (aydınlatmak, bilgilendirmek) doğru seçenektir.",
    },
    {
        "question_text": "The team's victory was largely ------- to their coach's unconventional training methods.",
        "options": {"A": "attributable", "B": "irrelevant", "C": "opposed", "D": "indifferent", "E": "unrelated"},
        "correct_option": "A",
        "ai_explanation": "Zaferin sebebinin antrenörün yöntemleri olduğu vurgulanıyor. 'Attributable to' (bir şeye bağlanabilir, atfedilebilir) kalıbı bağlama uyar.",
    },
    {
        "question_text": "The economist warned that the policy could have ------- consequences for small businesses across the country.",
        "options": {"A": "beneficial", "B": "dire", "C": "negligible", "D": "predictable", "E": "favorable"},
        "correct_option": "B",
        "ai_explanation": "Bir uyarı söz konusu olduğundan, sonuçların olumsuz/ciddi olması beklenir. 'Dire' (vahim, ciddi) bu uyarıyla tutarlıdır.",
    },
    {
        "question_text": "The artist's work was initially ------- by critics, but it later gained widespread recognition.",
        "options": {"A": "praised", "B": "dismissed", "C": "celebrated", "D": "rewarded", "E": "promoted"},
        "correct_option": "B",
        "ai_explanation": "'But it later gained recognition' zıtlığı, başlangıçta eserin küçümsendiğini/reddedildiğini gösterir. 'Dismissed' (reddedilmiş, önemsenmemiş) doğru seçenektir.",
    },
    {
        "question_text": "The new policy was designed to ------- bureaucratic delays and speed up the approval process.",
        "options": {"A": "perpetuate", "B": "eliminate", "C": "justify", "D": "complicate", "E": "ignore"},
        "correct_option": "B",
        "ai_explanation": "Onay sürecini hızlandırmak için bürokratik gecikmelerin ortadan kaldırılması gerekir. 'Eliminate' (ortadan kaldırmak) bu amaca uygundur.",
    },
    {
        "question_text": "The research team found that long-term exposure to high noise levels can ------- hearing ability significantly.",
        "options": {"A": "enhance", "B": "restore", "C": "impair", "D": "maintain", "E": "develop"},
        "correct_option": "C",
        "ai_explanation": "Yüksek gürültüye uzun süre maruz kalmak işitme yeteneğini olumsuz etkiler. 'Impair' (bozmak, zayıflatmak) bu olumsuz etkiyi ifade eder.",
    },
    {
        "question_text": "Her ------- response to the interviewer's question left the audience wondering about her true intentions.",
        "options": {"A": "straightforward", "B": "evasive", "C": "enthusiastic", "D": "detailed", "E": "sincere"},
        "correct_option": "B",
        "ai_explanation": "İzleyicinin gerçek niyetleri sorgulaması, cevabın belirsiz/kaçamak olduğunu gösterir. 'Evasive' (kaçamak) doğru seçenektir.",
    },
    {
        "question_text": "The bridge was built to ------- the two sides of the river that had been separated for centuries.",
        "options": {"A": "divide", "B": "connect", "C": "isolate", "D": "distinguish", "E": "compare"},
        "correct_option": "B",
        "ai_explanation": "Köprünün işlevi iki kıyıyı birbirine bağlamaktır. 'Connect' (bağlamak) doğru seçenektir.",
    },
    {
        "question_text": "The director's latest film received ------- reviews, with most critics praising its originality and depth.",
        "options": {"A": "mixed", "B": "scathing", "C": "mediocre", "D": "lukewarm", "E": "glowing"},
        "correct_option": "E",
        "ai_explanation": "Eleştirmenlerin özgünlüğü ve derinliği övmesi olumlu bir tablo çizer. 'Glowing' (parlak, coşkulu) bu övgüyle tutarlıdır.",
    },
    {
        "question_text": "Scientists are trying to ------- the effects of climate change by developing more efficient renewable energy sources.",
        "options": {"A": "intensify", "B": "counteract", "C": "overlook", "D": "celebrate", "E": "duplicate"},
        "correct_option": "B",
        "ai_explanation": "Bilim insanlarının amacı iklim değişikliğinin etkilerine karşı koymaktır. 'Counteract' (etkisini gidermek) bu amacı ifade eder.",
    },
    {
        "question_text": "The CEO's ------- leadership style encouraged employees to share ideas and take creative risks.",
        "options": {"A": "authoritarian", "B": "rigid", "C": "inclusive", "D": "indifferent", "E": "distant"},
        "correct_option": "C",
        "ai_explanation": "Çalışanları fikir paylaşmaya teşvik eden bir liderlik tarzı kapsayıcı bir yaklaşım gerektirir. 'Inclusive' (kapsayıcı) doğru seçenektir.",
    },
    {
        "question_text": "The organization's primary goal is to ------- the rights of underprivileged communities through legal advocacy.",
        "options": {"A": "undermine", "B": "uphold", "C": "suppress", "D": "ignore", "E": "question"},
        "correct_option": "B",
        "ai_explanation": "Dezavantajlı toplulukların haklarını hukuki savunuculukla korumak amaçlanıyor. 'Uphold' (desteklemek, korumak) bu amacı ifade eder.",
    },
    {
        "question_text": "The athlete's remarkable ------- after such a serious injury surprised even her doctors.",
        "options": {"A": "deterioration", "B": "recovery", "C": "withdrawal", "D": "confusion", "E": "isolation"},
        "correct_option": "B",
        "ai_explanation": "Ciddi bir sakatlıktan sonra doktorları bile şaşırtan durum iyileşmedir. 'Recovery' (iyileşme) doğru seçenektir.",
    },
    {
        "question_text": "The author's writing style is known for its ------- descriptions that paint vivid pictures in the reader's mind.",
        "options": {"A": "vague", "B": "sparse", "C": "vivid", "D": "dull", "E": "repetitive"},
        "correct_option": "C",
        "ai_explanation": "Okuyucunun zihninde canlı imgeler yaratan bir yazarlık stili dinamik açıklamalar içerir. 'Vivid' (canlı, etkileyici) doğru seçenektir.",
    },
    {
        "question_text": "The government's attempt to ------- the two rival factions ultimately failed due to deep-rooted mistrust.",
        "options": {"A": "alienate", "B": "reconcile", "C": "provoke", "D": "separate", "E": "eliminate"},
        "correct_option": "B",
        "ai_explanation": "Derin güvensizlik ortamında hükümet iki rakip grubu uzlaştırmaya çalışmıştır. 'Reconcile' (uzlaştırmak) doğru seçenektir.",
    },
    {
        "question_text": "Despite being ------- for decades, the small town suddenly became a popular tourist destination after a famous film was shot there.",
        "options": {"A": "overcrowded", "B": "prosperous", "C": "obscure", "D": "accessible", "E": "celebrated"},
        "correct_option": "C",
        "ai_explanation": "'Despite' zıtlık kurar: kasaba tanınmadan aniden popüler hale gelmiştir. 'Obscure' (tanınmamış) bu zıtlığa uyar.",
    },
    {
        "question_text": "The lawyer argued that the contract was ------- because one of the parties had signed it under duress.",
        "options": {"A": "binding", "B": "void", "C": "valid", "D": "enforceable", "E": "transparent"},
        "correct_option": "B",
        "ai_explanation": "Baskı altında imzalanan bir sözleşme geçersizdir. 'Void' (geçersiz, hükümsüz) bu durumu ifade eder.",
    },
    {
        "question_text": "The construction of the new highway will inevitably ------- the natural habitat of several protected species.",
        "options": {"A": "restore", "B": "disrupt", "C": "preserve", "D": "improve", "E": "expand"},
        "correct_option": "B",
        "ai_explanation": "Yeni bir otoyolun inşaatı doğal yaşam alanlarını olumsuz etkiler. 'Disrupt' (bozmak) bu olumsuz etkiyi ifade eder.",
    },
    {
        "question_text": "The software update was intended to ------- the security vulnerabilities that hackers had been exploiting.",
        "options": {"A": "create", "B": "expose", "C": "patch", "D": "ignore", "E": "publicize"},
        "correct_option": "C",
        "ai_explanation": "Güvenlik açıklarını kapatmak için yazılım güncellemesi yapılır. 'Patch' (yamalamak) bu teknik bağlama uyar.",
    },
    {
        "question_text": "The historical records were so ------- that researchers found it nearly impossible to piece together an accurate timeline.",
        "options": {"A": "detailed", "B": "comprehensive", "C": "fragmented", "D": "organized", "E": "accessible"},
        "correct_option": "C",
        "ai_explanation": "Doğru bir zaman çizelgesi oluşturmanın neredeyse imkânsız olması, kayıtların eksik/parçalı olduğunu gösterir. 'Fragmented' (parçalı) doğru seçenektir.",
    },
    {
        "question_text": "The two countries signed a ------- agreement to cooperate on matters of border security and trade.",
        "options": {"A": "unilateral", "B": "bilateral", "C": "internal", "D": "confidential", "E": "temporary"},
        "correct_option": "B",
        "ai_explanation": "İki ülke arasında imzalanan bir anlaşma ikili bir nitelik taşır. 'Bilateral' (ikili, iki taraflı) doğru seçenektir.",
    },
    {
        "question_text": "The philosopher's ideas were so ------- that they continue to influence thinkers even two centuries after his death.",
        "options": {"A": "irrelevant", "B": "outdated", "C": "profound", "D": "simplistic", "E": "contradictory"},
        "correct_option": "C",
        "ai_explanation": "İki yüzyıl sonra bile etkisini sürdüren fikirler derin ve kalıcı olmalıdır. 'Profound' (derin, köklü) doğru seçenektir.",
    },
    {
        "question_text": "The company decided to ------- its operations in three new countries to increase its global market share.",
        "options": {"A": "reduce", "B": "suspend", "C": "expand", "D": "relocate", "E": "evaluate"},
        "correct_option": "C",
        "ai_explanation": "Üç yeni ülkeye açılmak, faaliyetlerin genişletildiğini gösterir. 'Expand' (genişletmek) doğru seçenektir.",
    },
    {
        "question_text": "The documentary sought to ------- the myths surrounding the life of the controversial historical figure.",
        "options": {"A": "reinforce", "B": "debunk", "C": "create", "D": "celebrate", "E": "promote"},
        "correct_option": "B",
        "ai_explanation": "Tartışmalı bir tarihi figüre dair mitleri ele almak, onları çürütmek anlamına gelir. 'Debunk' (çürütmek) doğru seçenektir.",
    },
    {
        "question_text": "The volunteers worked ------- to provide food and shelter for those affected by the devastating earthquake.",
        "options": {"A": "reluctantly", "B": "tirelessly", "C": "carelessly", "D": "occasionally", "E": "indifferently"},
        "correct_option": "B",
        "ai_explanation": "Yıkıcı bir depremden etkilenenlere yardım eden gönüllülerin yorulmadan çalıştığı anlaşılmaktadır. 'Tirelessly' (yorulmaksızın) doğru seçenektir.",
    },
    {
        "question_text": "The young researcher's groundbreaking work in the field of genetics has ------- new possibilities for cancer treatment.",
        "options": {"A": "closed", "B": "ignored", "C": "limited", "D": "opened", "E": "questioned"},
        "correct_option": "D",
        "ai_explanation": "Öncü araştırmalar kanser tedavisinde yeni olanakların önünü açar. 'Opened' (açmak) bu bağlama uyar.",
    },
    {
        "question_text": "The proposal was ------- by the board after it became clear that it would not be financially viable.",
        "options": {"A": "approved", "B": "celebrated", "C": "rejected", "D": "modified", "E": "funded"},
        "correct_option": "C",
        "ai_explanation": "Mali açıdan sürdürülebilir olmayan bir teklif reddedilir. 'Rejected' (reddedilmiş) doğru seçenektir.",
    },
    {
        "question_text": "The journalist refused to ------- her sources, even under pressure from the authorities.",
        "options": {"A": "protect", "B": "reveal", "C": "contact", "D": "interview", "E": "appreciate"},
        "correct_option": "B",
        "ai_explanation": "Gazeteci baskı altında bile kaynağını açıklamamıştır; 'reveal' (açıklamak) doğru seçenektir. Cümle olumsuz anlamla kurulmuştur.",
    },
    {
        "question_text": "The ------- nature of the job, which required constant travel, eventually led her to seek a more stable position.",
        "options": {"A": "sedentary", "B": "nomadic", "C": "predictable", "D": "rewarding", "E": "local"},
        "correct_option": "B",
        "ai_explanation": "Sürekli seyahat gerektiren bir iş göçebe/yerinde durmayan bir nitelik taşır. 'Nomadic' (göçebe) doğru seçenektir.",
    },
    {
        "question_text": "The archaeologists were delighted to ------- a well-preserved ancient settlement beneath the city.",
        "options": {"A": "bury", "B": "destroy", "C": "discover", "D": "overlook", "E": "abandon"},
        "correct_option": "C",
        "ai_explanation": "Arkeologların heyecan duyması, iyi korunmuş bir yerleşim yeri bulmalarından kaynaklanır. 'Discover' (keşfetmek) doğru seçenektir.",
    },
    {
        "question_text": "The company's ------- approach to customer service set it apart from its competitors in the industry.",
        "options": {"A": "indifferent", "B": "exemplary", "C": "inconsistent", "D": "minimal", "E": "delayed"},
        "correct_option": "B",
        "ai_explanation": "Rakiplerinden ayrışmasını sağlayan bir müşteri hizmeti anlayışı örnek nitelikte olmalıdır. 'Exemplary' (örnek) doğru seçenektir.",
    },
    {
        "question_text": "The report revealed that the company had been ------- its financial records to mislead investors.",
        "options": {"A": "auditing", "B": "falsifying", "C": "improving", "D": "simplifying", "E": "publishing"},
        "correct_option": "B",
        "ai_explanation": "Yatırımcıları yanıltmak amacıyla yapılan işlem, mali kayıtların tahrif edilmesidir. 'Falsifying' (tahrif etmek) doğru seçenektir.",
    },
    {
        "question_text": "The two scientists worked ------- on the project, sharing data and regularly reviewing each other's progress.",
        "options": {"A": "independently", "B": "reluctantly", "C": "collaboratively", "D": "competitively", "E": "secretly"},
        "correct_option": "C",
        "ai_explanation": "Veri paylaşımı ve birbirlerinin ilerlemesini takip etmek iş birliğini gösterir. 'Collaboratively' (iş birliği içinde) doğru seçenektir.",
    },
    {
        "question_text": "The city council voted to ------- the historic district in order to protect its architectural heritage.",
        "options": {"A": "demolish", "B": "commercialize", "C": "preserve", "D": "expand", "E": "relocate"},
        "correct_option": "C",
        "ai_explanation": "Mimari mirası koruma amacı, tarihi bölgenin muhafaza edilmesini gerektirir. 'Preserve' (korumak) doğru seçenektir.",
    },
    {
        "question_text": "The new study ------- previous assumptions about the relationship between diet and mental health.",
        "options": {"A": "confirmed", "B": "challenged", "C": "ignored", "D": "repeated", "E": "simplified"},
        "correct_option": "B",
        "ai_explanation": "Yeni bir araştırmanın önceki varsayımlara yaklaşımı genellikle onları sorgulamak yönünde olur. 'Challenged' (sorgulamak) doğru seçenektir.",
    },
    {
        "question_text": "The child's ------- curiosity about the natural world eventually led him to pursue a career in biology.",
        "options": {"A": "fading", "B": "limited", "C": "insatiable", "D": "occasional", "E": "superficial"},
        "correct_option": "C",
        "ai_explanation": "Doğal dünyaya duyulan merakın biyoloji kariyerine yol açması, bu merakın doyumsuz/sınırsız olduğunu gösterir. 'Insatiable' (doyumsuz) doğru seçenektir.",
    },
    {
        "question_text": "The manager's tendency to ------- important decisions often caused frustration among team members.",
        "options": {"A": "rush", "B": "delegate", "C": "postpone", "D": "announce", "E": "document"},
        "correct_option": "C",
        "ai_explanation": "Önemli kararların sürekli ertelenmesi ekip üyelerinde hayal kırıklığı yaratır. 'Postpone' (ertelemek) doğru seçenektir.",
    },
    {
        "question_text": "The opposition party called for an ------- inquiry into the government's handling of public funds.",
        "options": {"A": "internal", "B": "independent", "C": "informal", "D": "incomplete", "E": "occasional"},
        "correct_option": "B",
        "ai_explanation": "Muhalefet partisi, kamu fonlarının kullanımını araştırmak için bağımsız bir soruşturma istemiştir. 'Independent' (bağımsız) doğru seçenektir.",
    },
    {
        "question_text": "The community came together to ------- a memorial in honor of those who lost their lives in the disaster.",
        "options": {"A": "demolish", "B": "ignore", "C": "erect", "D": "relocate", "E": "question"},
        "correct_option": "C",
        "ai_explanation": "Hayatını kaybedenleri anmak için topluluk bir anıt dikmiştir. 'Erect' (dikmek, inşa etmek) doğru seçenektir.",
    },
    {
        "question_text": "After years of ------- negotiations, the two companies finally agreed on the terms of the merger.",
        "options": {"A": "brief", "B": "productive", "C": "effortless", "D": "prolonged", "E": "unnecessary"},
        "correct_option": "D",
        "ai_explanation": "'After years of' ifadesi uzun süren bir süreci işaret eder. 'Prolonged' (uzun süren) bu zaman vurgusuna uygundur.",
    },
    {
        "question_text": "The diplomat's ------- choice of words prevented the situation from escalating into a full-scale diplomatic crisis.",
        "options": {"A": "careless", "B": "provocative", "C": "tactful", "D": "ambiguous", "E": "aggressive"},
        "correct_option": "C",
        "ai_explanation": "Diplomatik bir krizi önleyen kelime seçimi incelikli/diplomatik olmalıdır. 'Tactful' (nazik, incelikli) doğru seçenektir.",
    },
    {
        "question_text": "The children were ------- by the magician's performance and kept asking for more tricks.",
        "options": {"A": "bored", "B": "frightened", "C": "captivated", "D": "confused", "E": "disappointed"},
        "correct_option": "C",
        "ai_explanation": "Gösteriden sonra daha fazla numara istemeleri çocukların büyülendiğini gösterir. 'Captivated' (büyülenmiş) doğru seçenektir.",
    },
    {
        "question_text": "The results of the experiment were ------- and could not be explained by any existing scientific theory.",
        "options": {"A": "predictable", "B": "expected", "C": "anomalous", "D": "consistent", "E": "straightforward"},
        "correct_option": "C",
        "ai_explanation": "Mevcut hiçbir bilimsel teoriyle açıklanamayan sonuçlar anormal/sapkın sonuçlardır. 'Anomalous' (anormal) doğru seçenektir.",
    },
    {
        "question_text": "The foundation was established with the sole ------- of providing scholarships to students from low-income families.",
        "options": {"A": "condition", "B": "purpose", "C": "result", "D": "requirement", "E": "benefit"},
        "correct_option": "B",
        "ai_explanation": "Vakfın kurulmasının arkasındaki tek neden burs sağlamaktır. 'Purpose' (amaç) doğru seçenektir.",
    },
    {
        "question_text": "The treaty was signed as a ------- measure to prevent further conflict between the two nations.",
        "options": {"A": "retaliatory", "B": "provocative", "C": "preventive", "D": "symbolic", "E": "temporary"},
        "correct_option": "C",
        "ai_explanation": "Daha fazla çatışmayı önlemek amacıyla imzalanan antlaşma önleyici bir nitelik taşır. 'Preventive' (önleyici) doğru seçenektir.",
    },
    {
        "question_text": "The scientist's ------- approach to research, in which she questioned every assumption, led to several breakthrough discoveries.",
        "options": {"A": "conventional", "B": "rigorous", "C": "careless", "D": "superficial", "E": "rushed"},
        "correct_option": "B",
        "ai_explanation": "Her varsayımı sorgulayan ve çığır açan keşiflere yol açan bir araştırma anlayışı titiz olmalıdır. 'Rigorous' (titiz, sıkı) doğru seçenektir.",
    },
    {
        "question_text": "The severe drought has had a ------- impact on the agricultural sector, threatening food security in the region.",
        "options": {"A": "minimal", "B": "positive", "C": "negligible", "D": "devastating", "E": "temporary"},
        "correct_option": "D",
        "ai_explanation": "Gıda güvenliğini tehdit eden şiddetli bir kuraklık tarım sektörünü yıkıcı biçimde etkiler. 'Devastating' (yıkıcı) doğru seçenektir.",
    },
    {
        "question_text": "The student's essay was praised for its ------- argument and well-structured paragraphs.",
        "options": {"A": "incoherent", "B": "coherent", "C": "repetitive", "D": "incomplete", "E": "biased"},
        "correct_option": "B",
        "ai_explanation": "Övgü alan ve iyi yapılandırılmış bir deneme tutarlı/mantıklı bir argüman içerir. 'Coherent' (tutarlı) doğru seçenektir.",
    },
    {
        "question_text": "The board members remained ------- about the merger, insisting that more financial data was needed before making a decision.",
        "options": {"A": "enthusiastic", "B": "committed", "C": "skeptical", "D": "confident", "E": "satisfied"},
        "correct_option": "C",
        "ai_explanation": "Daha fazla veri talep etmek ve kararsız kalmak, yöneticilerin kuşkuyla yaklaştığını gösterir. 'Skeptical' (şüpheci) doğru seçenektir.",
    },
    {
        "question_text": "The new law was designed to ------- the activities of companies that had been polluting the river for years.",
        "options": {"A": "encourage", "B": "regulate", "C": "ignore", "D": "fund", "E": "expand"},
        "correct_option": "B",
        "ai_explanation": "Yıllardır nehri kirleten şirketlerin faaliyetlerini kontrol altına almak için yeni bir yasa çıkarılmıştır. 'Regulate' (düzenlemek) doğru seçenektir.",
    },
    {
        "question_text": "The patient was advised to ------- strenuous physical activity for at least six weeks following the surgery.",
        "options": {"A": "continue", "B": "pursue", "C": "avoid", "D": "monitor", "E": "increase"},
        "correct_option": "C",
        "ai_explanation": "Ameliyat sonrasında doktorlar genellikle ağır fiziksel aktiviteden uzak durulmasını önerir. 'Avoid' (kaçınmak) doğru seçenektir.",
    },
    {
        "question_text": "Despite her ------- schedule, the CEO always made time to meet with employees at all levels of the organization.",
        "options": {"A": "flexible", "B": "empty", "C": "hectic", "D": "predictable", "E": "manageable"},
        "correct_option": "C",
        "ai_explanation": "'Despite' zıtlık kurar: yoğun programa rağmen CEO çalışanlarla vakit ayırabilmiştir. 'Hectic' (çok yoğun) bu zıtlığa uyar.",
    },
    {
        "question_text": "The documentary provided a ------- account of the events leading up to the financial collapse of 2008.",
        "options": {"A": "biased", "B": "superficial", "C": "comprehensive", "D": "inaccurate", "E": "exaggerated"},
        "correct_option": "C",
        "ai_explanation": "2008 mali krizine giden süreci anlatan nitelikli bir belgesel kapsamlı bir anlatım sunar. 'Comprehensive' (kapsamlı) doğru seçenektir.",
    },
    {
        "question_text": "The new airport terminal was designed to ------- up to 50 million passengers per year.",
        "options": {"A": "restrict", "B": "accommodate", "C": "discourage", "D": "replace", "E": "reduce"},
        "correct_option": "B",
        "ai_explanation": "Terminalin yıllık 50 milyon yolcuya hizmet edecek şekilde tasarlanması kapasiteyi gündeme getirir. 'Accommodate' (ağırlamak) doğru seçenektir.",
    },
    {
        "question_text": "The speaker's ------- tone immediately put the audience at ease, making them feel comfortable enough to ask questions.",
        "options": {"A": "aggressive", "B": "condescending", "C": "reassuring", "D": "monotonous", "E": "intimidating"},
        "correct_option": "C",
        "ai_explanation": "İzleyiciyi rahatlatıp soru sormalarını sağlayan bir ses tonu güven verici olmalıdır. 'Reassuring' (güven verici) doğru seçenektir.",
    },
    {
        "question_text": "The professor urged students to ------- information from multiple sources rather than relying on a single textbook.",
        "options": {"A": "gather", "B": "ignore", "C": "memorize", "D": "reject", "E": "limit"},
        "correct_option": "A",
        "ai_explanation": "Tek bir kaynakla yetinmeden bilgi toplamak önerilmektedir. 'Gather' (toplamak) doğru seçenektir.",
    },
    {
        "question_text": "The researcher's ------- findings contradicted decades of established scientific consensus on the topic.",
        "options": {"A": "expected", "B": "preliminary", "C": "controversial", "D": "outdated", "E": "irrelevant"},
        "correct_option": "C",
        "ai_explanation": "Onlarca yıllık bilimsel uzlaşıyı çürüten bulgular tartışmalı/polemik yaratan nitelikte olmalıdır. 'Controversial' (tartışmalı) doğru seçenektir.",
    },
    {
        "question_text": "The new treatment proved ------- in reducing symptoms in over 90% of patients who participated in the clinical trial.",
        "options": {"A": "harmful", "B": "ineffective", "C": "effective", "D": "experimental", "E": "unnecessary"},
        "correct_option": "C",
        "ai_explanation": "Hastaların yüzde doksanından fazlasında belirtileri azaltmak, tedavinin etkili olduğunu gösterir. 'Effective' (etkili) doğru seçenektir.",
    },
    {
        "question_text": "The company's ------- to deliver the project on time damaged its reputation with the client.",
        "options": {"A": "ability", "B": "commitment", "C": "failure", "D": "success", "E": "determination"},
        "correct_option": "C",
        "ai_explanation": "Müşteriyle ilişkiyi zedeleyen durum, projenin zamanında teslim edilememesidir. 'Failure' (başarısızlık) doğru seçenektir.",
    },
    {
        "question_text": "His ------- behavior during the meeting made it clear that he was not fully committed to the project.",
        "options": {"A": "enthusiastic", "B": "diligent", "C": "passionate", "D": "apathetic", "E": "attentive"},
        "correct_option": "D",
        "ai_explanation": "Projeye tam olarak bağlı olmadığını ortaya koyan davranış ilgisizlik/umursamazlık göstergesidir. 'Apathetic' (ilgisiz, umursamaz) doğru seçenektir.",
    },
    {
        "question_text": "The government launched a campaign to ------- public awareness about the dangers of excessive sugar consumption.",
        "options": {"A": "reduce", "B": "ignore", "C": "raise", "D": "limit", "E": "question"},
        "correct_option": "C",
        "ai_explanation": "Tehlikeler hakkında kamuoyunu bilgilendirmek için farkındalığın artırılması gerekir. 'Raise' (artırmak, yükseltmek) doğru seçenektir.",
    },
    {
        "question_text": "The company's new product line was designed to ------- to a younger demographic that had previously been ignored.",
        "options": {"A": "appeal", "B": "object", "C": "refer", "D": "apply", "E": "conform"},
        "correct_option": "A",
        "ai_explanation": "Daha önce göz ardı edilen genç bir kitleye yönelik ürün hattı, o kitleye hitap etmek için tasarlanmıştır. 'Appeal to' (hitap etmek, çekici gelmek) doğru seçenektir.",
    },
    {
        "question_text": "The historian's book was praised for its ------- research and its ability to bring a forgotten era to life.",
        "options": {"A": "superficial", "B": "biased", "C": "meticulous", "D": "hurried", "E": "incomplete"},
        "correct_option": "C",
        "ai_explanation": "Unutulmuş bir dönemi canlandıran ve övgü alan tarih kitabının araştırması titiz/ayrıntılı olmalıdır. 'Meticulous' (titiz, özenli) doğru seçenektir.",
    },
    {
        "question_text": "The two sides reached a ------- agreement that, while not perfect, was acceptable to both parties.",
        "options": {"A": "definitive", "B": "comprehensive", "C": "compromise", "D": "unilateral", "E": "binding"},
        "correct_option": "C",
        "ai_explanation": "Mükemmel olmasa da her iki tarafın kabul ettiği bir anlaşma uzlaşmayı temsil eder. 'Compromise' (uzlaşma, taviz verme) doğru seçenektir.",
    },
    {
        "question_text": "The prime minister's ------- remarks about the opposition party sparked a heated debate in parliament.",
        "options": {"A": "conciliatory", "B": "inflammatory", "C": "diplomatic", "D": "cautious", "E": "ambiguous"},
        "correct_option": "B",
        "ai_explanation": "Parlamentoda sert bir tartışma başlatan açıklamalar kışkırtıcı/ateşleyici nitelikte olmalıdır. 'Inflammatory' (kışkırtıcı) doğru seçenektir.",
    },
    {
        "question_text": "The environmental group ------- the government's plan to build a new coal-fired power plant.",
        "options": {"A": "supported", "B": "funded", "C": "opposed", "D": "designed", "E": "welcomed"},
        "correct_option": "C",
        "ai_explanation": "Çevre grubu, yeni bir kömür santralinin inşasına karşı çıkmıştır. 'Opposed' (karşı çıkmak) doğru seçenektir.",
    },
    {
        "question_text": "The ------- between the two theories lies in their fundamentally different assumptions about human behavior.",
        "options": {"A": "similarity", "B": "connection", "C": "distinction", "D": "overlap", "E": "relationship"},
        "correct_option": "C",
        "ai_explanation": "İki teori arasındaki temelden farklı varsayımlar, aralarındaki ayrımı/farkı ortaya koyar. 'Distinction' (ayrım, fark) doğru seçenektir.",
    },
    {
        "question_text": "The village had been ------- for years before a new road brought it closer to the rest of the country.",
        "options": {"A": "connected", "B": "isolated", "C": "developed", "D": "populated", "E": "accessible"},
        "correct_option": "B",
        "ai_explanation": "Yeni bir yol yapılana kadar ülkenin geri kalanından kopuk olan köy izole/tecrit edilmiş durumdaydı. 'Isolated' (izole edilmiş) doğru seçenektir.",
    },
    {
        "question_text": "The surgeon's ------- skill and calm demeanor during the complex operation reassured both the patient and the medical team.",
        "options": {"A": "amateur", "B": "questionable", "C": "exceptional", "D": "average", "E": "developing"},
        "correct_option": "C",
        "ai_explanation": "Karmaşık bir operasyonda hem hastayı hem de ekibi rahatlatan bir cerrah olağanüstü yeteneklere sahip olmalıdır. 'Exceptional' (olağanüstü) doğru seçenektir.",
    },
    {
        "question_text": "The company's ------- to adapt to changing market conditions ultimately led to its downfall.",
        "options": {"A": "ability", "B": "willingness", "C": "failure", "D": "commitment", "E": "strategy"},
        "correct_option": "C",
        "ai_explanation": "Değişen pazar koşullarına uyum sağlayamamak şirketin çöküşüne yol açmıştır. 'Failure' (başarısızlık, yetersizlik) doğru seçenektir.",
    },
    {
        "question_text": "The teacher's ------- feedback helped the students understand exactly where they needed to improve.",
        "options": {"A": "vague", "B": "discouraging", "C": "constructive", "D": "delayed", "E": "irrelevant"},
        "correct_option": "C",
        "ai_explanation": "Öğrencilerin tam olarak neyi geliştirmeleri gerektiğini anlamalarına yardımcı olan geri bildirim yapıcı nitelikte olmalıdır. 'Constructive' (yapıcı) doğru seçenektir.",
    },
    {
        "question_text": "The administration's new policy was ------- by human rights organizations for its potential to restrict freedom of expression.",
        "options": {"A": "praised", "B": "welcomed", "C": "endorsed", "D": "condemned", "E": "celebrated"},
        "correct_option": "D",
        "ai_explanation": "İfade özgürlüğünü kısıtlama potansiyeli taşıyan bir politika insan hakları örgütleri tarafından kınanır. 'Condemned' (kınamak) doğru seçenektir.",
    },
    {
        "question_text": "The ------- of the new vaccine against the virus was confirmed through a series of rigorous clinical trials.",
        "options": {"A": "failure", "B": "cost", "C": "efficacy", "D": "availability", "E": "complexity"},
        "correct_option": "C",
        "ai_explanation": "Klinik denemelerle doğrulanan şey aşının virüse karşı etkinliği/başarısıdır. 'Efficacy' (etkinlik, verimlilik) doğru seçenektir.",
    },
    {
        "question_text": "The local government decided to ------- the use of single-use plastics in an effort to reduce environmental pollution.",
        "options": {"A": "encourage", "B": "subsidize", "C": "ban", "D": "promote", "E": "ignore"},
        "correct_option": "C",
        "ai_explanation": "Çevre kirliliğini azaltmak için tek kullanımlık plastiklerin kullanımının yasaklanması en uygun önlemdir. 'Ban' (yasaklamak) doğru seçenektir.",
    },
    {
        "question_text": "The findings of the investigation were ------- with the testimonies of the eyewitnesses, strengthening the case.",
        "options": {"A": "inconsistent", "B": "contradictory", "C": "consistent", "D": "unrelated", "E": "incompatible"},
        "correct_option": "C",
        "ai_explanation": "Davayı güçlendiren bulgular, görgü tanıklarının ifadeleriyle örtüşmelidir. 'Consistent' (tutarlı, örtüşen) doğru seçenektir.",
    },
    {
        "question_text": "The renowned architect's design for the new museum was both ------- and functional, impressing critics worldwide.",
        "options": {"A": "ordinary", "B": "costly", "C": "outdated", "D": "innovative", "E": "controversial"},
        "correct_option": "D",
        "ai_explanation": "Tüm dünyada eleştirmenleri etkileyen hem işlevsel hem de özgün bir tasarım yenilikçi olmalıdır. 'Innovative' (yenilikçi) doğru seçenektir.",
    },
    {
        "question_text": "The manager ------- the new employee for her outstanding performance during the first month on the job.",
        "options": {"A": "criticized", "B": "ignored", "C": "commended", "D": "dismissed", "E": "questioned"},
        "correct_option": "C",
        "ai_explanation": "Olağanüstü performans için yeni çalışanın takdir edilmesi/övülmesi beklenir. 'Commended' (takdir etmek, övmek) doğru seçenektir.",
    },
    {
        "question_text": "The charity's annual report showed that its programs had ------- the lives of thousands of people in need.",
        "options": {"A": "worsened", "B": "complicated", "C": "transformed", "D": "ignored", "E": "limited"},
        "correct_option": "C",
        "ai_explanation": "Binlerce ihtiyaç sahibinin hayatına dokunan programlar o hayatları köklü biçimde değiştirmiştir. 'Transformed' (dönüştürmek) doğru seçenektir.",
    },
    {
        "question_text": "The politician's ------- remarks were taken out of context and misrepresented in several news reports.",
        "options": {"A": "deliberate", "B": "offhand", "C": "formal", "D": "prepared", "E": "scripted"},
        "correct_option": "B",
        "ai_explanation": "Bağlamdan koparılıp çarpıtılan açıklamalar, hazırlıksız/gelişigüzel yapılan yorumlar olmalıdır. 'Offhand' (düşünmeden, gelişigüzel) doğru seçenektir.",
    },
    {
        "question_text": "The economic crisis led many skilled workers to ------- abroad in search of better employment opportunities.",
        "options": {"A": "remain", "B": "migrate", "C": "retire", "D": "invest", "E": "settle"},
        "correct_option": "B",
        "ai_explanation": "Ekonomik kriz, nitelikli işçileri daha iyi iş imkânları için yurt dışına göç etmeye yöneltmiştir. 'Migrate' (göç etmek) doğru seçenektir.",
    },
    {
        "question_text": "The ancient ruins were so ------- that archaeologists spent years trying to identify which civilization had built them.",
        "options": {"A": "familiar", "B": "well-documented", "C": "modern", "D": "enigmatic", "E": "accessible"},
        "correct_option": "D",
        "ai_explanation": "Hangi medeniyete ait olduğu yıllarca araştırılan kalıntılar gizemli/bulmaca niteliğindedir. 'Enigmatic' (gizemli, esrarengiz) doğru seçenektir.",
    },
    {
        "question_text": "The training program was specifically designed to ------- employees with the skills needed for the digital economy.",
        "options": {"A": "deprive", "B": "equip", "C": "distract", "D": "discourage", "E": "burden"},
        "correct_option": "B",
        "ai_explanation": "Çalışanların dijital ekonomi için gereken becerilerle donatılması, eğitim programının amacıdır. 'Equip' (donatmak) doğru seçenektir.",
    },
    {
        "question_text": "The public was ------- when the investigation revealed that officials had known about the safety risks for years.",
        "options": {"A": "indifferent", "B": "unsurprised", "C": "outraged", "D": "relieved", "E": "amused"},
        "correct_option": "C",
        "ai_explanation": "Yetkililerin tehlikeyi yıllarca gizlediğinin ortaya çıkması halkta öfke yaratmıştır. 'Outraged' (öfkeli, kızmış) doğru seçenektir.",
    },
    {
        "question_text": "The policy reform was long ------- by experts who had been warning about the flaws in the existing system for years.",
        "options": {"A": "opposed", "B": "criticized", "C": "overdue", "D": "unexpected", "E": "celebrated"},
        "correct_option": "C",
        "ai_explanation": "Yıllardır uyarı yapan uzmanlar için bu reform çok geç yapılmış/gecikmiş bir adımdır. 'Overdue' (gecikmiş, çoktan yapılması gereken) doğru seçenektir.",
    },
    {
        "question_text": "The company's ------- growth over the past decade has made it one of the most valuable brands in the world.",
        "options": {"A": "sluggish", "B": "inconsistent", "C": "stagnant", "D": "exponential", "E": "minimal"},
        "correct_option": "D",
        "ai_explanation": "On yıl içinde dünyanın en değerli markalarından biri olmak üssel/hızla katlanarak artan bir büyümeyi gerektirir. 'Exponential' (üssel, katlanarak artan) doğru seçenektir.",
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
        raise HTTPException(status_code=400, detail="Geçerli bir email ve en az 6 karakterli bir şifre girmelisin.")

    user_id = create_user(email, hash_password(payload.password))
    if user_id is None:
        raise HTTPException(status_code=400, detail="Bu email zaten kayıtlı.")

    # Doğrulama emaili gönder
    token = create_email_token(user_id, "verify", expires_minutes=60)
    send_verification_email(email, token)

    jwt = create_token(user_id)
    return TokenResponse(
        access_token=jwt,
        user=UserOut(id=user_id, email=email, solved_count=0, correct_count=0, is_verified=False),
    )


@app.post("/api/login", response_model=TokenResponse)
def login(payload: UserLogin):
    email = payload.email.strip().lower()
    row = get_user_by_email(email)
    if not row or not verify_password(payload.password, row[2]):
        raise HTTPException(status_code=401, detail="Email veya şifre hatalı.")

    user_id, user_email, _hash, solved_count, correct_count, is_verified = row
    token = create_token(user_id)
    return TokenResponse(
        access_token=token,
        user=UserOut(id=user_id, email=user_email, solved_count=solved_count, correct_count=correct_count, is_verified=is_verified),
    )


@app.get("/api/me", response_model=UserOut)
def get_me(user_id: int = Depends(get_current_user_id)):
    row = get_user_by_id(user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
    uid, email, _hash, solved_count, correct_count, is_verified = row
    return UserOut(id=uid, email=email, solved_count=solved_count, correct_count=correct_count, is_verified=is_verified)


@app.get("/api/resend-verification")
def resend_verification(user_id: int = Depends(get_current_user_id)):
    """Doğrulama emailini tekrar gönderir."""
    row = get_user_by_id(user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
    uid, email, _hash, solved_count, correct_count, is_verified = row
    if is_verified:
        return {"message": "Email zaten doğrulanmış."}
    token = create_email_token(uid, "verify", expires_minutes=60)
    send_verification_email(email, token)
    return {"message": "Doğrulama emaili gönderildi."}


@app.get("/verify-email", response_class=HTMLResponse)
def verify_email(token: str):
    """Email doğrulama linki burada işlenir."""
    user_id = use_email_token(token, "verify")
    if not user_id:
        return HTMLResponse("""
        <html><body style="font-family:Inter,sans-serif;background:#0b0f19;color:#f8fafc;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;">
        <div style="text-align:center;">
            <div style="font-size:48px;">❌</div>
            <h2 style="color:#f87171;">Geçersiz veya süresi dolmuş link</h2>
            <p style="color:#94a3b8;">Lütfen tekrar doğrulama emaili isteyin.</p>
            <a href="/" style="color:#38bdf8;">← Ana sayfaya dön</a>
        </div></body></html>
        """, status_code=400)
    verify_user_email(user_id)
    return HTMLResponse("""
    <html><body style="font-family:Inter,sans-serif;background:#0b0f19;color:#f8fafc;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;">
    <div style="text-align:center;">
        <div style="font-size:48px;">✅</div>
        <h2 style="color:#34d399;">Email adresin doğrulandı!</h2>
        <p style="color:#94a3b8;">Artık YDS Mentor AI'ı tam olarak kullanabilirsin.</p>
        <a href="/" style="display:inline-block;margin-top:20px;background:#38bdf8;color:#0f172a;padding:12px 24px;border-radius:10px;text-decoration:none;font-weight:700;">
            Uygulamaya Git →
        </a>
    </div></body></html>
    """)


@app.post("/api/forgot-password")
def forgot_password(payload: UserLogin):
    """Şifre sıfırlama emaili gönderir. (payload'dan sadece email kullanılır)"""
    email = payload.email.strip().lower()
    row = get_user_by_email(email)
    # Güvenlik: kullanıcı yoksa da aynı mesajı ver (email enumeration önlemi)
    if row:
        token = create_email_token(row[0], "reset", expires_minutes=60)
        send_password_reset_email(email, token)
    return {"message": "Kayıtlı bir hesap varsa şifre sıfırlama emaili gönderildi."}


@app.post("/api/reset-password")
def reset_password(token: str, payload: UserRegister):
    """Şifre sıfırlama tokenini doğrular ve yeni şifreyi kaydeder."""
    user_id = use_email_token(token, "reset")
    if not user_id:
        raise HTTPException(status_code=400, detail="Geçersiz veya süresi dolmuş link.")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Şifre en az 6 karakter olmalı.")
    update_user_password(user_id, hash_password(payload.password))
    return {"message": "Şifren başarıyla güncellendi. Giriş yapabilirsin."}


@app.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(token: str):
    """Şifre sıfırlama sayfasını gösterir."""
    return HTMLResponse(f"""
    <html><head><title>Şifre Sıfırla - YDS Mentor AI</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ font-family:Inter,sans-serif;background:#0b0f19;color:#f8fafc;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0; }}
        .card {{ background:rgba(30,41,59,0.4);padding:40px;border-radius:20px;border:1px solid rgba(255,255,255,0.08);width:100%;max-width:360px; }}
        h2 {{ margin-bottom:8px;font-size:20px; }}
        p {{ color:#94a3b8;font-size:13px;margin-bottom:24px; }}
        input {{ width:100%;box-sizing:border-box;padding:12px 14px;margin-bottom:12px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.1);border-radius:10px;color:#f8fafc;font-size:14px;font-family:inherit; }}
        input:focus {{ outline:none;border-color:#38bdf8; }}
        button {{ background:#38bdf8;color:#0f172a;border:none;padding:14px;font-size:15px;font-weight:700;border-radius:10px;cursor:pointer;width:100%; }}
        .msg {{ margin-top:12px;font-size:13px;text-align:center; }}
    </style></head>
    <body><div class="card">
        <h2>🔑 Yeni Şifre Belirle</h2>
        <p>En az 6 karakterli yeni şifreni gir.</p>
        <input type="password" id="pw" placeholder="Yeni şifre">
        <input type="password" id="pw2" placeholder="Şifreyi tekrarla">
        <button onclick="doReset()">Şifremi Güncelle</button>
        <div class="msg" id="msg"></div>
    </div>
    <script>
        async function doReset() {{
            const pw = document.getElementById('pw').value;
            const pw2 = document.getElementById('pw2').value;
            const msg = document.getElementById('msg');
            if (pw !== pw2) {{ msg.style.color='#f87171'; msg.innerText='Şifreler eşleşmiyor.'; return; }}
            if (pw.length < 6) {{ msg.style.color='#f87171'; msg.innerText='En az 6 karakter olmalı.'; return; }}
            const res = await fetch('/api/reset-password?token={token}', {{
                method:'POST', headers:{{'Content-Type':'application/json'}},
                body: JSON.stringify({{email:'placeholder@x.com', password:pw}})
            }});
            const data = await res.json();
            if (res.ok) {{
                msg.style.color='#34d399';
                msg.innerHTML = data.message + ' <a href="/" style="color:#38bdf8;">Giriş yap →</a>';
            }} else {{
                msg.style.color='#f87171'; msg.innerText = data.detail || 'Bir hata oluştu.';
            }}
        }}
    </script></body></html>
    """)


@app.get("/admin", response_class=HTMLResponse)
def admin_panel(secret: str = ""):
    """Admin paneli — kullanıcı listesi."""
    if secret != ADMIN_SECRET:
        return HTMLResponse("<h2 style='font-family:sans-serif;padding:40px;color:red;'>❌ Yetkisiz erişim.</h2>", status_code=403)
    users = get_all_users()
    rows = ""
    for u in users:
        uid, email, is_verified, solved, correct, created_at = u
        ratio = f"{round(correct/solved*100)}%" if solved > 0 else "—"
        verified = "✅" if is_verified else "⏳"
        rows += f"<tr><td>{uid}</td><td>{email}</td><td>{verified}</td><td>{solved}</td><td>{ratio}</td><td>{str(created_at)[:16]}</td></tr>"
    return HTMLResponse(f"""
    <html><head><title>Admin - YDS Mentor AI</title>
    <style>
        body {{ font-family:Inter,sans-serif;background:#0b0f19;color:#f8fafc;padding:40px;margin:0; }}
        h1 {{ color:#38bdf8;margin-bottom:24px; }}
        table {{ width:100%;border-collapse:collapse; }}
        th {{ background:rgba(56,189,248,0.1);padding:12px;text-align:left;font-size:13px;color:#38bdf8;border-bottom:1px solid rgba(255,255,255,0.08); }}
        td {{ padding:12px;font-size:13px;border-bottom:1px solid rgba(255,255,255,0.04); }}
        tr:hover td {{ background:rgba(255,255,255,0.02); }}
    </style></head>
    <body>
        <h1>🛡️ Admin Paneli</h1>
        <p style="color:#64748b;margin-bottom:24px;">Toplam kullanıcı: <strong style="color:#f8fafc">{len(users)}</strong></p>
        <table>
            <tr><th>ID</th><th>Email</th><th>Doğrulandı</th><th>Çözülen</th><th>Başarı</th><th>Kayıt Tarihi</th></tr>
            {rows}
        </table>
    </body></html>
    """)


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
    uid, email, _hash, solved_count, correct_count, is_verified = urow
    return UserOut(id=uid, email=email, solved_count=solved_count, correct_count=correct_count, is_verified=is_verified)


@app.get("/api/next-question")
def next_question(user_id: int = Depends(get_current_user_id)):
    """
    Kullanıcıya sıradaki soruyu gönderir. Eğer kullanıcının emaili onaylanmamışsa
    ve 5 sorudan fazla çözmüşse hata döndürür.
    """
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı.")
    
    uid, email, _hash, solved_count, correct_count, is_verified = user

    # 1. DOĞRULAMA KONTROLÜ (5 SORU LİMİTİ)
    if not is_verified and solved_count >= 5:
        return {"error": "limit_reached"}

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
    çağrılmak üzere tasarlanmıştır.
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


@app.post("/api/ask-mentor")
def ask_mentor(payload: AskMentorRequest, user_id: int = Depends(get_current_user_id)):
    """
    Kullanıcının soru hakkında Gemini AI'a soru sormasını sağlayan Mentor sistemi.
    """
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="Yapay zeka (Gemini API) henüz sisteme bağlanmadı.")

    # Sorunun orijinal verilerini veritabanından çek
    row = get_question_by_id(payload.question_id)
    if not row:
        raise HTTPException(status_code=404, detail="Soru bulunamadı.")
        
    q_id, q_text, q_options, q_correct, q_expl = row

    # Yapay zekaya verilecek Prompt (Sufle)
    prompt = f"""
    Sen, YDS sınavına hazırlanan öğrencilere yardım eden "YDS Mentor AI" adında uzman ve tatlı dilli bir İngilizce öğretmenisin. 
    Öğrenci şu an aşağıdaki soruyu çözdü:
    
    - Soru: {q_text}
    - Şıklar: {q_options}
    - Doğru Cevap: {q_correct}
    - Sistemdeki Hazır Açıklama: {q_expl}

    Öğrencinin kafasına bir şey takıldı ve sana şunu soruyor: "{payload.user_message}"

    Lütfen öğrencinin bu sorusuna doğrudan, samimi ve anlaşılır bir Türkçe ile cevap ver. 
    Cevabın çok uzun olmasın, öğrencinin sorduğu spesifik noktaya (kelimenin anlamına, gramer yapısına vb.) odaklan.
    """

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return {"answer": response.text}
    except Exception as e:
        print(f"[AI ERROR]: {e}")
        raise HTTPException(status_code=500, detail="Yapay zeka şu an meşgul, lütfen birazdan tekrar dene.")


@app.get("/", response_class=HTMLResponse)
def read_index():
    if not INDEX_FILE.exists():
        return HTMLResponse(
            "🌀 Hata: 'index.html' dosyası bulunamadı! "
            "Lütfen main.py ile aynı klasörde olduğundan emin ol.",
            status_code=500,
        )
    return INDEX_FILE.read_text(encoding="utf-8")
