
# Macro Economics Tracker v2
## Production-focused PRD / Tracking UX Spec
- 업데이트 날짜: 2026-03-06
- 문서 목적: **저비용 MVP에서 시작해 production까지 갈 수 있는 real-time macro / market intelligence tracker**를 설계한다.
- 이번 리비전에서 반영한 것:
  - `macro`를 **경제 예측 엔진**이 아니라 **경제 관련 이슈를 추적·구조화·설명하는 product**로 재정의
  - **저비용 LLM 라우팅 전략** 반영 (`gpt-5-mini` 중심, `gpt-5-nano` 보조)
  - **Hetzner + Postgres + pgvector** 중심 인프라로 재설계
  - **Neo4j는 day-1 필수 아님**으로 정리
  - agent 간 통신은 **JSON schema**를 기본으로 확정
  - 가장 중요한 차별화 포인트를 **tracking UX**로 재설계

---

# 0. 먼저 한 문장으로: 지금 뭘 만드는가

이 제품은 **“경제를 예측하는 AI”**가 아니라,  
**“경제/정책/시장 관련 뉴스와 공식 문서를 실시간으로 추적해서, 같은 이슈를 하나의 story로 묶고, 무엇이 바뀌었는지/왜 중요한지/근거가 뭔지를 빠르게 보여주는 tracking system”**이다.

즉, 이 프로젝트의 본질은:

- forecasting engine이 아니라
- search engine만도 아니고
- generic news summarizer도 아닌

**real-time story tracking + evidence-backed sensemaking system**이다.

---

# 1. Executive summary

## 1.1 핵심 제품 가설

현재 시장의 강한 제품들은 공통적으로 **watchlist / dashboard / alerts / summaries / event signals**를 제공한다.  
AlphaSense는 dashboard, watchlist, saved search, alerts, Smart Summaries를 중심으로 monitoring workflow를 만들고 있고, LSEG는 Watchlist Pulse와 event calendar를 통해 watchlist-centered monitoring을 강화하고 있으며, Dataminr는 geovisualization으로 unfolding event를 빠르게 파악하게 하고, Event Registry는 event clustering과 timeline/visualization으로 story 탐색을 돕는다. RavenPack과 S&P Capital IQ Pro는 structured signals와 multi-document analysis를 강화하고 있다. [M1][M2][M3][M4][M5][M6][M7][M8][M9]

**하지만 여기서 여전히 차별화할 수 있는 포인트는 "tracking UX"다.**

현재 제품군에서 자주 보이는 패턴은:
- query / watchlist / saved search를 중심으로 구성됨
- alert가 기사 단위로 쏟아지기 쉬움
- 서로 다른 종류의 사건(예: CPI 발표 vs 지정학 충격 vs 중앙은행 발언)을 비슷한 화면/피드에서 다룸
- story가 시간에 따라 **어떻게 상태가 바뀌었는지**를 직관적으로 보여주는 UX는 제한적
- evidence drill-down이 있어도 대체로 **요약 → 원문 문서** 레벨에 머무르고, **문장/claim → span** 레벨 추적은 약한 경우가 많음

이 문서의 핵심 제안은 다음 4가지다.

1. **Track를 1급 객체로 만들 것**
   - 검색이나 feed가 아니라 **Track**가 제품의 기본 단위가 되어야 함
2. **Mode-aware Tracking UX**
   - 같은 “뉴스 추적”이라도 사건 종류에 따라 UX가 달라져야 함
3. **Episode-based Alerts**
   - 기사 알림이 아니라 **story 상태 변화 알림**으로 바꿔 alert fatigue를 줄일 것
4. **Evidence-first + progressive disclosure**
   - AI 설명은 항상 근거와 함께 나오고, 자세한 설명은 점진적으로 열리게 해야 함

## 1.2 최종 제품 포지셔닝

> **Macro Economics Tracker = Evidence-first, mode-aware, real-time story tracking OS for macro and market-moving information**

## 1.3 이번 리비전의 최종 의사결정

| 항목 | 결정 |
|---|---|
| 핵심 차별점 | 검색보다 **tracking UX** |
| LLM 기본 모델 | `gpt-5-mini` |
| 저비용 보조 모델 | `gpt-5-nano` |
| 임베딩 | `text-embedding-3-small` |
| reasoning 사용 원칙 | **전 단계에 reasoning을 깔지 말고**, 애매한 해석/작성/검증 단계에만 사용 |
| infra | Hetzner 위에 `FastAPI + Next.js + Redis + Postgres + pgvector` |
| graph DB | **초기에는 미사용**, 필요해지면 read-model로 Neo4j 추가 |
| agent protocol | **JSON schema** |
| user-facing output | UI + concise narrative + evidence drawer |
| real-time transport | **SSE 우선**, 협업/양방향 편집 필요할 때만 WebSocket |
| queue | MVP/lean production은 Redis 기반, 이후 필요시 NATS/JetStream 등으로 확장 |
| notification philosophy | **article alert가 아니라 state-change alert** |

---

# 2. 시장 조사 업데이트: 현재 툴들은 tracking을 어떻게 다루는가

## 2.1 AlphaSense: dashboard / watchlist / alerts / summaries 중심

AlphaSense 공식 문서와 도움말을 보면, dashboard, watchlist, saved searches, ongoing alerts, Smart Summaries가 monitoring workflow의 중심이다. Dashboard는 중앙에서 여러 정보 스트림을 한 번에 보게 해 주고, watchlist는 여러 회사를 하나의 관찰 단위로 묶고, alerts는 highlighted statements와 context를 포함해 관련 문서로 되돌아가게 한다. [M1][M2][M3][M4]

**배울 점**
- monitoring을 “검색의 부가기능”이 아니라 **항상 켜진 workflow**로 다룸
- watchlist + dashboard 조합은 강력함
- alert에 **context와 highlighted statements**를 넣는 건 매우 중요

**남는 기회**
- watchlist / saved search를 넘어 **story-centric tracking object**로 추상화할 수 있음
- track type에 따라 다른 화면을 자동 제안하는 adaptive UX는 아직 더 밀어붙일 여지가 큼

## 2.2 LSEG: watchlist pulse + events calendar + consolidated event workflows

LSEG 공식 자료를 보면 Workspace와 관련 앱들은 Watchlist Pulse, customized watchlist views, event calendar, consolidated event search UX를 제공한다. 특히 watchlist 대상의 significant activity를 24x7로 알려주고, 일정형 이벤트는 customized calendar로 본다. [M5][M6][M7][M8]

**배울 점**
- tracking은 “무슨 기사가 떴나?”보다 **내 watchlist에 무슨 변화가 생겼나?**로 보는 게 강력함
- 일정형 이벤트는 list보다 **calendar UX**가 더 자연스럽다
- consolidated view는 analyst에게 중요

**남는 기회**
- schedule-driven events와 breaking events를 더 명확히 다른 UX로 분기할 수 있음
- watchlist를 entity list로만 두지 않고 **driver x entity matrix**로 확장 가능

## 2.3 Dataminr: geovisualization + unfolding-event context

Dataminr 공식 자료는 geovisualization, custom views, event unfolding analysis를 강조한다. 실시간 alert를 지도와 맥락 계층으로 보여주어 event를 더 actionable하게 만든다. [M9][M10]

**배울 점**
- 사건이 위치/시설/국경/경로와 깊게 연결될 때는 map이 압도적으로 강함
- 실시간 alert만 던지는 것이 아니라 **어떻게 사건이 전개되었는지** 보여줘야 함

**남는 기회**
- 매크로/시장 intelligence에서 geo view를 “지정학·공급망·자산 노출”까지 더 깊게 결합 가능
- map만 보여주는 게 아니라 **entity exposure / asset exposure / contagion path**까지 보여줄 수 있음

## 2.4 Event Registry: event clustering + timeline/map/category visualization

Event Registry는 기사들을 entity/topic/event로 annotation하고, online clustering으로 같은 사건을 묶고, timeline / map / source locations / categories 등 다양한 시각화로 탐색하도록 한다. [M11][M12]

**배울 점**
- article이 아니라 **event cluster**가 중요한 추상화라는 점은 이미 검증됨
- story browsing과 visual exploration의 기반이 있다

**남는 기회**
- clustering은 해주지만, **사용자 작업 흐름(what changed / why it matters / what next)**까지 UX를 밀어붙인 제품 기획은 아직 더 강화 가능
- long-running theme를 운영/협업 가능한 **track object**로 다듬는 데 기회가 있음

## 2.5 RavenPack / S&P Capital IQ Pro: structured signals + multi-document intelligence

RavenPack은 entity/event 단위 relevance, novelty, impact를 구조화하고, S&P Capital IQ Pro는 AI-powered search, Document Intelligence, sentiment scores, transcript summarization, multi-document analysis를 강조한다. [M13][M14][M15]

**배울 점**
- low-level signal 자체는 이미 commoditized되어 가고 있음
- 사용자가 원하는 건 raw signal이 아니라 **decision-ready synthesis**임

**남는 기회**
- structured signal을 UX에서 **priority, state-change, contradiction, exposure**로 번역하는 부분
- multi-doc intelligence를 **track memory**와 결합하는 부분

---

# 3. 제품 전략: 어디서 이길 것인가

## 3.1 핵심 전략 문장

> **기존 툴이 “search + watchlist + alerts + summaries”를 제공한다면, 우리는 “track + state + evidence + memory”를 제공한다.**

## 3.2 차별화 포인트 4개

### D1. Query-first가 아니라 Track-first
대부분의 툴은 search / watchlist / saved search가 시작점이다.  
우리는 사용자가 **지속적으로 돌보고 싶은 문제 단위**를 `Track`로 만든다.

예:
- “US inflation”
- “Fed 2026 easing path”
- “China property stress”
- “Taiwan Strait tension”
- “Semiconductor supply chain disruptions”
- “EUR/USD에 영향 주는 ECB communication”

이 Track는 단순 키워드 묶음이 아니라:
- entities
- themes
- geographies
- assets
- alert policy
- memory window
- mode
- lens
를 포함하는 **stateful monitoring object**다.

### D2. One-size-fits-all feed가 아니라 Mode-aware surfaces
같은 “tracking”이라도 다음은 서로 다른 UX가 필요하다.

- CPI 발표 같은 **scheduled release**
- Fed speech 같은 **policy communication**
- 전쟁/재난/제재 같은 **breaking shock**
- China growth worries 같은 **slow-burn theme**
- portfolio-linked risk 같은 **watchlist / exposure monitoring**

현재 시장에서는 watchlist/feed/dashboard가 강하지만,  
**사건 유형마다 다른 tracking surface를 기본 제공하는 것**이 차별화 포인트가 될 수 있다. 이건 LSEG의 calendar, Dataminr의 geo, Event Registry/newsLens의 timeline에서 각기 힌트를 얻되, 하나의 product 안에서 통합하는 전략이다. [M6][M9][M11][P1]

### D3. Article alert가 아니라 Episode / state-change alert
alert fatigue 연구는 모니터링/보안 시스템에서 과도한 비핵심 alert가 사용자의 피로와 무시를 낳는다고 정리한다. [P2]  
뉴스 소비 맥락에서도 Reuters Institute는 selective news avoidance를 강조한다. [P3]

따라서 이 제품은 “기사 몇 개 떴다”가 아니라,
- story state changed
- confidence increased
- official confirmation appeared
- market reaction confirmed
- contradiction emerged
같은 **의미 있는 변화**만 알려줘야 한다.

### D4. Evidence-first + progressive disclosure
explainability UX 연구는 progressive disclosure가 trust calibration과 user control에 도움이 될 수 있다고 제안한다. [P4]  
data storytelling 연구는 narrative가 comprehension efficiency와 일부 insight effectiveness를 높일 수 있다고 보여준다. [P5]

따라서:
- 상단에는 짧은 narrative
- 한 단계 아래에는 evidence snippets
- 더 깊게 들어가면 full source / span / graph
로 이어지는 **점진적 공개 구조**가 필요하다.

---

# 4. 핵심 개념 설계: Track, Story, Episode, Evidence

## 4.1 정보 단위 계층

이 제품의 data/UX 계층은 아래처럼 분리한다.

```text
Document
→ Evidence Span
→ Event
→ Story / Episode
→ Track
→ Workspace / Team View
```

### Document
개별 기사, 연설문, 보도자료, 보고서

### Evidence Span
문서 안에서 실제 근거가 되는 문장/절/span

### Event
“누가 무엇을 했다” 수준의 구조화된 사건
- 예: “Fed governor signaled slower cuts”
- 예: “US CPI exceeded expectations”

### Story / Episode
여러 event와 문서가 모여 이루는 의미 있는 흐름
- 예: “US inflation re-acceleration concerns”
- 예: “ECB signals prolonged restrictive stance”

### Track
사용자가 지속적으로 관찰하는 문제 공간
- 예: “US inflation”
- 이 안에 여러 Story / Episode가 생기고 식고 갈라지고 합쳐진다

## 4.2 왜 Track가 중요하냐

기존 제품들이 잘하는 것은:
- search
- watchlist
- alerts
- summary

하지만 실제 analyst workflow는 이렇게 흘러간다.

1. 내가 계속 보고 싶은 주제가 있다
2. 그 주제에서 지금 무슨 일이 바뀌었는지 알고 싶다
3. 이유와 근거를 빠르게 확인하고 싶다
4. 비슷한 과거 사례와 연결하고 싶다
5. 다른 사람에게 briefing으로 넘기고 싶다

이 연속된 흐름은 **query**보다 **track**라는 제품 객체로 잡아야 구현이 쉬워진다.

## 4.3 Track schema (conceptual)

```json
{
  "track_id": "trk_us_inflation",
  "title": "US Inflation",
  "mode": "slow_burn_theme",
  "default_lens": "economist",
  "entities": ["Federal Reserve", "BLS", "United States"],
  "themes": ["inflation", "rates", "labor"],
  "assets": ["USD", "UST2Y", "SPX"],
  "regions": ["US"],
  "alert_policy": {
    "notify_on_state_change": true,
    "notify_on_official_release": true,
    "daily_digest": true
  },
  "memory_window_days": 365,
  "priority": "high"
}
```

---

# 5. UX North Star: UI보다 중요한 것

## 5.1 UX 핵심 문장

> **사용자는 뉴스 100개를 보고 싶어 하는 게 아니라, “내가 봐야 할 변화 3개”를 이해하고 싶어 한다.**

## 5.2 30-3-10 UX Rule

이 제품의 모든 tracking UX는 아래를 만족해야 한다.

### 30초 안에
사용자는 아래 4가지를 알아야 한다.
- 뭐가 바뀌었지?
- 왜 이게 떴지?
- 왜 중요한지?
- 지금 근거가 충분한지?

### 3분 안에
사용자는 아래를 끝낼 수 있어야 한다.
- 사건 흐름 파악
- 관련 주체 파악
- contradiction 여부 확인
- 다음에 봐야 할 trigger 확인

### 10분 안에
사용자는 아래를 할 수 있어야 한다.
- 동료에게 briefing 공유
- analyst note 추가
- watch / mute / escalate 결정
- 유사 과거 사례 비교

이 30-3-10 rule은 단순히 화면 예쁘게 만드는 문제보다 훨씬 중요하다.  
이게 곧 **tracking UX의 operational definition**이다.

## 5.3 UX 원칙 8개

### U1. “왜 내가 이걸 보고 있는지”를 항상 보여줘라
모든 카드/alert/detail에서 `Why this surfaced`가 있어야 한다.

### U2. “무슨 문서를 읽어야 하냐”보다 “무슨 변화가 있었냐”를 먼저 보여줘라
문서 feed는 2차 화면이다.

### U3. 사건 유형마다 기본 surface를 다르게 하라
release / speech / shock / theme / watchlist는 한 화면에 억지로 맞추지 않는다.

### U4. alert는 기사 수가 아니라 상태 변화 기준으로 보내라
alert fatigue를 줄인다. [P2]

### U5. AI narrative는 항상 근거 한 클릭 거리여야 한다
supporting span, contradictory span, source spread가 바로 열려야 한다.

### U6. 사용자 역할에 따라 “보여주는 순서”를 바꿔라
같은 데이터라도 Economist, PM, Risk, Research의 entry point는 달라야 한다.

### U7. memory와 handoff를 first-class로 넣어라
“지난번 이 이슈는 어떻게 끝났더라?”가 바로 보여야 한다.

### U8. 적극적인 요약보다 좋은 triage가 더 중요하다
사용자는 요약이 아니라 **우선순위 정리**에 돈을 낸다.

---

# 6. 진짜 차별화 포인트: Mode-aware Tracking UX

이 섹션이 이 문서의 핵심이다.

## 6.1 왜 mode-aware여야 하나

현재 툴들을 보면:
- LSEG는 calendar에 강점이 있다
- Dataminr는 geovisualization에 강점이 있다
- Event Registry / newsLens 계열은 timeline / story에 강점이 있다
- AlphaSense는 dashboard / watchlist / alerts에 강점이 있다 [M2][M6][M9][M11][P1]

즉, 이미 시장은 “모든 걸 한 가지 list UI로 해결하지 않는다”는 힌트를 주고 있다.  
하지만 이걸 **하나의 adaptive tracking product**로 통합한 UX는 여전히 제품 기회가 있다.

우리는 이를 **Track Mode + Lens** 체계로 설계한다.

- **Mode** = 사건 타입에 따라 기본 surface를 정하는 것
- **Lens** = 사용자 역할/작업에 따라 모듈 우선순위를 바꾸는 것

## 6.2 Track Modes (핵심 제안)

### Mode A. Scheduled Release Mode
예:
- CPI / PPI / Payrolls / GDP / PMI / FOMC decision

#### 사용자의 핵심 질문
- 발표가 기대 대비 어땠나?
- 이전 값/수정치 대비 뭐가 바뀌었나?
- 시장은 어떻게 반응했나?
- 다음 trigger는 뭔가?

#### 기본 UX
- countdown ribbon
- consensus vs actual vs previous
- revision panel
- official release snippet
- market reaction strip
- “what changed” auto-summary
- 이전 6회 발표 mini history

#### 왜 이 UX가 필요한가
일정형 이벤트는 generic feed보다 **calendar + countdown + surprise decomposition**이 훨씬 직관적이다. LSEG가 customized calendar를 제공하는 이유도 같다. [M6]

#### 추천 UI block
- **Top bar**: T-5min / Released / Revised
- **Primary card**: actual vs expected
- **Driver cards**: subcomponents
- **Reaction strip**: yields, FX, equities, oil
- **Evidence drawer**: official release / first-wave coverage / analyst notes

#### alert 규칙
- T-60m optional
- T-5m optional
- 발표 직후
- revision 발생 시
- market reaction threshold 초과 시

#### 이 mode의 UX 차별화 포인트
- “기사”를 따라가는 게 아니라 **발표 lifecycle**을 따라감
- release 전/후 UI가 자연스럽게 이어짐

---

### Mode B. Policy Communication Mode
예:
- Fed speech
- ECB press release
- minutes
- regulatory consultation
- policy paper

#### 사용자의 핵심 질문
- stance가 바뀌었나?
- 새로 등장한 표현은 뭐고, 빠진 표현은 뭔가?
- 누가 어떤 톤으로 말했나?
- policy path에 어떤 의미가 있나?

#### 기본 UX
- statement diff
- hawkish / dovish shift indicator
- quote chips by theme
- prior speech / prior meeting compare
- speaker timeline
- “new phrase / removed phrase” box

#### 왜 이 UX가 필요한가
정책/커뮤니케이션 문서는 사건이 아니라 **언어의 변화**가 중요하다.  
일반 뉴스처럼 list로 보여주면 가장 중요한 차이(표현 변화, 톤 변화, 주제 가중치 변화)를 놓친다.

#### 추천 UI block
- **Header summary**: stance shift
- **Diff panel**: added / removed / softened / strengthened phrases
- **Quote evidence lane**
- **Cross-meeting compare**
- **Open questions**: what market still doesn't know

#### alert 규칙
- stance score 변화량이 threshold 초과
- new policy concept 등장
- market narrative와 official language가 충돌
- 새로운 high-authority speaker 등장

#### 이 mode의 UX 차별화 포인트
- generic summarization 대신 **language-diff UX**를 핵심으로 둠
- user가 “왜 hawkish라고 판단했는지”를 바로 볼 수 있음

---

### Mode C. Breaking Shock Mode
예:
- 전쟁/군사 충돌
- 제재 발표
- 자연재해
- 공급망 붕괴
- 대형 outage / cyber incident
- 갑작스러운 규제/정책 충격

#### 사용자의 핵심 질문
- 이거 진짜인가?
- 어디에서 벌어졌나?
- 누가 영향을 받나?
- 얼마나 심각한가?
- 아직 확인 안 된 건 뭔가?

#### 기본 UX
- confidence ladder (rumor → corroborated → official)
- live episode thread
- geo map / blast radius
- exposure panel
- contradiction panel
- chronology view

#### 왜 이 UX가 필요한가
이런 사건은 시간순 기사 list보다 **verification + geography + exposure**가 더 중요하다. Dataminr가 geovisualization을 강조하는 이유와 맞닿아 있다. [M9][M10]

#### 추천 UI block
- **State ladder**
- **Map + impacted assets/sites/entities**
- **Source corroboration count**
- **Contradictions tab**
- **Event timeline**
- **Escalation / handoff card**

#### alert 규칙
- confidence state transition
- official confirmation
- watched geography/entity overlap
- severity escalation
- follow-on event 발생

#### 이 mode의 UX 차별화 포인트
- “빨리 알림”만이 아니라 **빨리 믿을 수 있게** 만드는 UX
- 지도는 단순 decoration이 아니라 verification과 exposure reasoning의 중심

---

### Mode D. Slow-Burn Theme Mode
예:
- inflation re-acceleration
- China growth stress
- global supply chain normalization reversal
- energy transition investment slowdown

#### 사용자의 핵심 질문
- 이 theme가 커지고 있나, 식고 있나?
- narrative가 어느 phase에 있나?
- 누가 새로 들어왔고, 어떤 branch가 생겼나?
- disagreement가 커지고 있나?

#### 기본 UX
- heatline (volume / novelty / disagreement / confidence)
- storyline lanes
- branch / merge visualization
- phase labels
- strongest new evidence since last visit
- past analogs / memory lane

#### 왜 이 UX가 필요한가
long-running theme는 newsLens처럼 lane-based timeline이 강력하고, story navigation이 중요하다. [P1]  
generic card list는 “요즘 이 theme가 어떻게 진화하고 있는지”를 전달하기 어렵다.

#### 추천 UI block
- **Theme status bar**: heating / stable / cooling
- **Storyline lanes**
- **What changed since your last visit**
- **Top new evidence**
- **Similar past episode cards**
- **Disagreement / uncertainty panel**

#### alert 규칙
- phase change
- novelty spike
- disagreement spike
- high-authority source join
- watched asset overlap

#### 이 mode의 UX 차별화 포인트
- 지금 시장 툴의 대다수는 alert와 feed에 강하지만,
  우리는 **narrative evolution UX**를 product 중심에 둔다

---

### Mode E. Watchlist / Exposure Mode
예:
- 내가 신경 쓰는 국가/기업/상품/섹터 묶음
- 포트폴리오 연관 watchlist
- 공급망 노출 리스트

#### 사용자의 핵심 질문
- 내 관심 대상 중 누가 지금 attention이 필요한가?
- 어떤 macro driver 때문에 그런가?
- 다음 scheduled trigger가 뭐지?
- 어떤 story가 여러 대상에 동시에 영향을 주고 있나?

#### 기본 UX
- entity x driver matrix
- pulse badges
- upcoming trigger calendar
- top affecting tracks
- grouped alerts by watchlist

#### 왜 이 UX가 필요한가
watchlist는 list로 볼 수도 있지만, 실제로는 “무엇 때문에 영향을 받는가”가 중요하다.  
LSEG/AlphaSense가 watchlist monitoring을 잘하고 있다는 사실은 이 feature 수요를 보여준다. [M2][M5][M7]

#### 추천 UI block
- **Heat matrix**
- **Upcoming events rail**
- **Grouped impact cards**
- **Watchlist-level summary**
- **Driver filter**: rates / inflation / labor / FX / oil / geopolitics / regulation

#### alert 규칙
- entity priority score 상승
- same story가 multiple watched entities에 동시 영향
- upcoming release proximity
- exposure-specific contradiction or confirmation

#### 이 mode의 UX 차별화 포인트
- entity list를 **driver-aware matrix**로 바꾼다
- 사용자는 “무슨 뉴스가 있었지?”보다 “내 것 중 뭐가 위험해졌지?”를 본다

---

## 6.3 Lens: 같은 track라도 보는 순서를 바꾸자

각 Track는 Mode 외에도 Lens를 가진다.

### Economist Lens
우선순위:
1. official release / statements
2. revisions / subcomponents
3. stance / topic shifts
4. historical comparison
5. disagreement

### PM Lens
우선순위:
1. affected assets
2. market reaction strip
3. next catalyst
4. scenario impact
5. strongest evidence

### Risk Lens
우선순위:
1. confidence / corroboration
2. geography / counterparties / exposure
3. contradiction
4. escalation potential
5. action queue

### Research Lens
우선순위:
1. narrative evolution
2. similar past episodes
3. internal notes
4. evidence diversity
5. unresolved questions

**중요한 점:**  
Lens는 완전히 다른 제품을 만드는 게 아니라,  
**같은 data model 위에서 module ordering과 summary framing을 바꾸는 것**이다.  
이 방식이 UX는 좋아지면서 backend는 복잡해지지 않는 균형점이다.

---

# 7. 정보 구조와 사용자 흐름

## 7.1 Home = “My Tracks”, not “Latest Articles”

홈은 기사 feed가 아니라 **내 Track의 상태판**이어야 한다.

### Home 섹션 제안
1. **Needs Attention**
   - 최근 state change 발생
2. **Scheduled Soon**
   - 곧 다가오는 release / meeting
3. **Heating Up**
   - slow-burn themes 중 가열 중
4. **Watchlist Pressure**
   - watched entities에 동시 영향 주는 이슈
5. **Handoffs / Analyst Notes**
   - 팀 내 인수인계

### Track card가 꼭 포함해야 할 정보
- current state
- what changed
- why this surfaced
- why it matters
- next watch item
- confidence
- evidence count / source diversity
- mute / snooze / escalate

### 나쁜 예
- 제목 + source + timestamp만 있는 카드

### 좋은 예
- `US Inflation | Heating Up`
- `What changed: CPI-related stories gained official confirmation + 2Y yields reacted`
- `Why it matters: pushes cut expectations later`
- `Watch next: Powell speech in 4h`
- `Confidence: High | 7 independent sources`

## 7.2 Track Detail = 하나의 문제를 끝까지 파고드는 화면

Track detail은 다음 세 가지를 동시에 만족해야 한다.
- 빠른 orientation
- deep investigation
- handoff preparation

### 공통 상단 구조
1. **What changed**
2. **Why it matters**
3. **What to watch**
4. **State / confidence / source diversity badges**

### 공통 중단 구조
- mode-specific module
- storyline / timeline
- evidence drawer
- contradictions tab
- notes / memory lane

### 공통 하단 구조
- similar past episodes
- analyst annotations
- export / share briefing

## 7.3 Tracking Composer = differentiator

많은 툴은 saved search, watchlist, query builder로 시작한다.  
우리는 `Tracking Composer`를 만든다.

### Step 1. 무엇을 추적하나요?
- theme
- scheduled release
- policy actor
- geography
- watchlist

### Step 2. 어떤 방식으로 변화를 보고 싶나요?
- scheduled
- policy
- breaking
- slow-burn
- watchlist/exposure

### Step 3. 무엇이 중요하다고 보나요?
- official confirmation
- high-authority sources only
- market reaction threshold
- contradiction spike
- new geography/entity involved

### Step 4. 어떻게 받고 싶나요?
- live
- digest
- pre-event reminder
- quiet hours
- official-only push

이 Composer 자체가 UX differentiator다.  
사용자가 query syntax를 배우지 않아도 **problem-centric track**를 만들 수 있다.

---

# 8. Notification UX: alert fatigue를 막아야 제품이 산다

## 8.1 기본 원칙
- **한 story에 대해 기사 10개 알림 보내지 않는다**
- 같은 의미의 coverage는 collapse한다
- alert는 state transition 또는 priority jump가 있을 때만 보낸다
- alert는 항상 “왜 이게 떴는지”를 한 줄로 설명한다

## 8.2 Alert unit = Article가 아니라 Episode update

### 좋은 alert 예시
- “US CPI track moved from Planned → Released”
- “Taiwan shipping disruption track: confidence moved to Official”
- “Fed stance track: hawkishness shifted up vs previous speech”
- “China growth stress track: disagreement spiked after official denial”

### 나쁜 alert 예시
- “Reuters published article...”
- “Bloomberg published article...”
- “Another article mentions inflation...”

## 8.3 추천 alert 정책

### Immediate
- state transition
- official confirmation
- contradiction emergence
- severe exposure overlap

### Digest
- slow-burn trend summaries
- watchlist recap
- daily top track changes

### Quiet / suppress
- duplicates
- low-authority repetition
- non-meaningful wording changes
- story state가 변하지 않은 반복 coverage

## 8.4 Alert card에 꼭 있어야 할 것
- track title
- state change
- 1-line why
- confidence
- top evidence
- open unresolved question
- quick actions: open / snooze / mute / share

---

# 9. Evidence UX: trust를 만드는 진짜 인터랙션

## 9.1 Evidence Drawer는 선택이 아니라 필수
AI summary가 아무리 좋아도, 사용자 입장에선 결국:
- “근거 어딨는데?”
- “이건 사실이야, 추론이야?”
- “반대 기사도 있나?”
를 본다.

## 9.2 Evidence Drawer 구성 제안

### Tab 1. Support
- 이 문장을 지지하는 evidence spans
- source별로 분리
- official source 먼저

### Tab 2. Contradictions
- 상반된 보도 / 불확실성
- low confidence 영역 표시

### Tab 3. Source Spread
- 몇 개의 독립 source가 있는지
- official / wire / local / blog 구분

### Tab 4. Model Notes
- observed fact vs model inference
- extraction confidence
- 왜 이런 state로 판단했는지

## 9.3 Progressive disclosure
상단 summary에서는 간단하게 보이고,  
클릭하면 sentence-level evidence, 더 클릭하면 원문 span, 더 클릭하면 full document로 내려간다.

이게 explainability 연구가 말하는 progressive disclosure와 잘 맞는다. [P4]

## 9.4 Summary template
모든 auto-generated summary는 아래 구조를 따른다.

1. **Observed fact**
2. **Why it matters**
3. **What to watch**
4. **Open question**

각 문장은 `support_level`을 가진다.
- supported
- inferred
- unresolved

---

# 10. Memory / Handoff UX: 이건 진짜 제품 가치가 된다

대부분의 뉴스 툴은 “지금”은 보여주지만,  
팀이 몇 주/몇 달 동안 같은 이슈를 따라가며 지식을 축적하는 UX는 약하다.

## 10.1 Memory Lane
Track detail 하단에 아래를 둔다.
- similar past episodes
- 이전 비슷한 state transition
- 과거 결과 요약
- 당시 잘 맞았던 / 틀렸던 해석

## 10.2 Handoff Note
팀 협업을 위해 track마다 간단한 handoff note를 둔다.
- current thesis
- things we know
- things unresolved
- next check time
- owner

## 10.3 Snapshot / Briefing
Track는 언제든지 snapshot으로 저장 가능해야 한다.
- timestamped summary
- evidence pack
- key charts / key quotes
- notes included

이렇게 해야 “어제/지난주에 우리가 왜 그렇게 판단했는지”를 추적할 수 있다.

---

# 11. Production architecture (lean but real)

이 섹션은 **Hetzner 기준, 과하게 무겁지 않지만 production 운영 가능한 설계**를 목표로 한다.

## 11.1 권장 스택

### Frontend
- **Next.js + TypeScript**
- 이유:
  - 빠른 UI 개발
  - SSR/streaming 대응
  - dashboard / detail / auth 연동 편함

### Backend API
- **FastAPI**
- 이유:
  - Python LLM stack과 잘 맞음
  - JSON schema validation / Pydantic 강함
  - worker와 코드 공유 쉬움

### Worker / Job execution
- Python worker pool
- 초기는 **Redis + arq / Celery** 수준으로 충분
- queue 인터페이스를 추상화해두고, 나중에 NATS/JetStream 등으로 교체 가능하게 설계

### Database
- **PostgreSQL 16 + pgvector**
- system of record는 Postgres
- vector similarity는 pgvector
- full-text search는 Postgres FTS부터 시작
- relations도 SQL table로 관리

### Cache / realtime fanout
- **Redis**
- cache + job queue + lightweight pub/sub

### Object storage
- **S3-compatible storage**
- Hetzner Object Storage 또는 MinIO
- raw docs / snapshots / exports 저장

### Realtime updates
- **SSE(Server-Sent Events)** 우선
- 이유:
  - dashboard 갱신이 주로 one-way
  - WebSocket보다 구현/운영 단순
- 협업 presence, live co-editing이 필요해지면 WebSocket 추가

### Observability
- OpenTelemetry
- Prometheus + Grafana
- Loki
- Sentry

### Deployment
- 초기: Docker Compose on Hetzner
- 이후 팀/트래픽이 커지면 k3s / Nomad / managed Postgres로 이동

## 11.2 왜 이 스택이 맞나

이 프로젝트의 복잡성은 “infra complexity”보다 **information complexity**에 있다.  
따라서 day-1에 Kubernetes, Kafka, Neo4j, separate vector DB, multiple agent protocols를 다 넣으면 실패 확률이 올라간다.

**원칙**
- 먼저 product complexity를 푼다
- infra는 필요한 지점까지 단순하게 유지한다
- system of record는 하나(Postgres)로 유지한다

---

# 12. Source strategy: 저비용이지만 real-time처럼 보이게

## 12.1 추천 source mix

### 필수 공식 source
- Federal Reserve RSS [M16]
- ECB RSS [M17]
- BLS release calendar [M18]

### 저비용 / 무료 source
- GDELT open data [M19]

### 선택적 확장
- Event Registry / NewsAPI.ai (paid enrichment)
- premium news wires
- internal notes / research memos

## 12.2 source lane 설계
모든 story는 source lane을 분리해 보여준다.

- Official
- Media / wire
- Market reaction
- Internal notes

이 lane 분리가 중요하다.  
사용자는 “official confirmation이 나왔는지”와 “시장 해석이 어떻게 붙었는지”를 분리해서 보고 싶어한다.

---

# 13. Agent architecture: multi-agent지만 swarm으로 가지 않는다

## 13.1 핵심 원칙
- 자유방임 agent swarm 금지
- **supervisor + deterministic pipeline + selective LLM use**
- 각 agent는 작은 책임과 명확한 JSON schema를 가진다

## 13.2 추천 agent 구성

### A. Source Scout
역할:
- RSS/API polling
- raw source 저장
- source metadata 부착

LLM:
- 없음

### B. Relevance Triage
역할:
- 문서가 현재 active track들과 관련 있는지 1차 판정
- priority 낮은 문서 제거

우선순위:
1. rules / taxonomy / source type
2. embeddings similarity
3. 애매하면 `gpt-5-nano`

모델 추천 이유:
`gpt-5-nano`는 빠르고 저렴하며 summarization/classification 용도에 적합하다. [M20][M21]

### C. Event Extractor
역할:
- who / what / when / where / trigger / effect 추출
- evidence spans 생성
- observed fact와 inference 분리

모델:
- 기본 `gpt-5-mini`

이유:
well-defined structured extraction에 적합하고, nano보다 안정적이다. [M22][M23]

### D. Entity Linker
역할:
- alias canonicalization
- entity type tagging
- region / asset / theme mapping

우선순위:
1. alias dictionary
2. embedding match
3. 애매하면 `gpt-5-nano`
4. 더 애매하면 `gpt-5-mini`

### E. Story Matcher
역할:
- 새 event가 기존 story에 붙는지 판단
- 새 story / episode 생성

우선순위:
1. embedding + time window + entity overlap
2. borderline case만 `gpt-5-mini`

### F. Writer / Briefing Agent
역할:
- what changed / why it matters / what to watch
- track card summary
- briefing draft

모델:
- `gpt-5-mini`

### G. Verifier
역할:
- summary sentence와 evidence span 정합성 점검
- unsupported / inferred / contradictory flag

모델:
- `gpt-5-mini`

### H. Escalation Agent (optional)
역할:
- analyst가 요청한 deep brief
- cross-track synthesis
- scenario write-up

초기 MVP:
- 생략 가능
- 필요시 상위 모델을 on-demand로만 사용

## 13.3 LLM routing policy

### 절대 하지 말 것
- 모든 기사에 mini 돌리기
- 모든 단계 reasoning-heavy 모델 쓰기
- dedupe, sort, schedule 같은 deterministic 작업까지 LLM에 맡기기

### 기본 정책
- 먼저 rule / SQL / embeddings로 줄인다
- 애매한 의미 해석에만 LLM 사용
- writer와 verifier에 budget을 더 준다
- triage는 싸게, final user-facing quality는 조금 더 투자

---

# 14. 모델 선택: 최신 의사결정

## 14.1 추천 모델 세트

| 용도 | 추천 모델 | 이유 |
|---|---|---|
| triage / cheap classification | `gpt-5-nano` | 빠르고 가장 저렴한 GPT-5 계열, summarization/classification 적합 [M20][M21] |
| structured extraction / story writing / verification | `gpt-5-mini` | well-defined tasks에 적합한 faster, cost-efficient GPT-5 [M22][M23] |
| embeddings | `text-embedding-3-small` | 저비용 similarity / clustering 용도 적합 [M24] |

## 14.2 모델 사용 철학
- reasoning은 “크게 많이” 필요하지 않다
- 이 시스템의 핵심은 **문서 구조화와 tracking UX**
- high-end reasoning model은 analyst-requested deep brief나 complex synthesis에만 제한적으로 사용

## 14.3 비용/품질 상식
OpenAI 공식 가격표 기준으로 `gpt-5-mini`는 `gpt-5-nano`보다 비싸지만, extraction / writing / verification 같은 사용자 체감 품질 영역에서 더 안전하다. [M23]  
따라서:
- 많은 양의 분류/triage는 nano
- 사용자에게 노출되는 문장과 schema 품질이 중요한 곳은 mini
가 기본값이다.

---

# 15. Agent contract: JSON이 답이다

## 15.1 Markdown이 아니라 JSON이어야 하는 이유
agent 간 통신은 사람이 읽기 좋은 prose가 아니라,
- 파싱 가능해야 하고
- validation 가능해야 하고
- retry 가능해야 하고
- DB에 바로 넣을 수 있어야 한다

따라서 **JSON schema**가 맞다.

## 15.2 A2A protocol은 왜 지금 안 쓰나
A2A는 서로 다른 시스템/벤더/에이전트 생태계 간 상호운용성이 필요할 때 유용하다.  
하지만 이 프로젝트의 초중기 단계는:
- 단일 팀이
- 단일 코드베이스를 운영하고
- 내부 agent를 orchestration 하는 상황이다

이 경우 A2A는 과하다.  
초기에는:
- internal JSON contracts
- versioned schemas
- queue jobs
로 충분하다.

## 15.3 권장 schema 원칙
모든 agent output에 아래가 있어야 한다.

- `schema_version`
- `trace_id`
- `source_document_ids`
- `evidence_span_ids`
- `confidence`
- `produced_at`
- `producer`
- `support_level`

## 15.4 예시: event_extraction.v1

```json
{
  "schema_version": "event_extraction.v1",
  "trace_id": "trc_01JQ...",
  "document_id": "doc_123",
  "events": [
    {
      "event_id": "evt_1",
      "actor_entities": ["ent_fed"],
      "action": "signaled slower cuts",
      "target_entities": [],
      "themes": ["rates", "inflation"],
      "regions": ["US"],
      "time_ref": "2026-03-06T13:00:00Z",
      "support_level": "supported",
      "confidence": 0.88,
      "evidence_span_ids": ["esp_7", "esp_9"]
    }
  ],
  "produced_at": "2026-03-06T13:01:20Z",
  "producer": "event_extractor"
}
```

## 15.5 예시: story_update.v1

```json
{
  "schema_version": "story_update.v1",
  "trace_id": "trc_01JQ...",
  "story_id": "sty_us_infl_12",
  "state_before": "heating",
  "state_after": "active",
  "what_changed": "Official CPI release confirmed earlier inflation concerns.",
  "why_it_matters": "The release may push policy easing expectations later.",
  "what_to_watch": "Fed speakers, 2Y yield reaction, next PPI release.",
  "support_level": "mixed_supported_and_inferred",
  "confidence": 0.84,
  "evidence_span_ids": ["esp_1", "esp_7", "esp_12"],
  "source_document_ids": ["doc_1", "doc_9"],
  "produced_at": "2026-03-06T13:02:00Z",
  "producer": "writer_verifier"
}
```

---

# 16. Data architecture: Postgres가 중심, graph는 나중에

## 16.1 핵심 결정
**system of record는 Postgres**로 간다.

### 이유
- transactions
- metadata filters
- timeline queries
- joins
- pgvector
- full-text
를 한 곳에서 다룰 수 있다.

## 16.2 핵심 테이블 제안

### documents
- source_id
- url
- title
- body
- published_at
- fetched_at
- canonical_hash
- source_type (official/media/internal)

### evidence_spans
- document_id
- span_text
- start_offset
- end_offset
- span_type (quote/fact/table/caution)

### entities
- canonical_name
- entity_type
- region
- asset_tags

### entity_aliases
- entity_id
- alias

### events
- story_id
- event_type
- event_time
- confidence
- support_level

### event_entity_edges
- event_id
- entity_id
- role (actor/target/location/asset)

### stories
- title
- mode
- current_state
- hotness
- confidence
- first_seen
- last_seen

### story_state_transitions
- story_id
- from_state
- to_state
- reason
- occurred_at

### tracks
- title
- mode
- default_lens
- alert_policy_json
- owner/team

### track_story_matches
- track_id
- story_id
- relevance_score
- actionability_score

### summaries
- story_id
- track_id
- what_changed
- why_it_matters
- what_to_watch

### annotations
- track_id / story_id
- author
- note_type
- note_text

## 16.3 pgvector는 어떻게 쓰나
- document embeddings
- story embeddings
- track embeddings
- similar past episodes retrieval
- triage candidate selection

## 16.4 Neo4j는 언제 쓰나
초기에는 안 쓴다.

### Neo4j를 뒤늦게 붙이는 조건
아래가 제품의 핵심이 되면 read-model로 붙인다.
- multi-hop graph exploration이 주요 UX
- graph path query가 잦음
- entity-event-theme relation browsing이 product headline feature가 됨

### 권장 방식
- day-1부터 Neo4j를 source of truth로 두지 않는다
- Postgres에서 정규화된 edge table을 만들고
- 필요해지면 비동기 sync로 Neo4j read replica를 만든다

즉,
> **graph UX는 필요하지만, graph DB가 day-1 필수는 아니다.**

---

# 17. Tracking logic: state machine이 UX를 결정한다

## 17.1 Story state machine (generic)

```text
candidate
→ corroborating
→ active
→ peak
→ cooling
→ dormant
→ resolved
```

### 보조 flag
- official_confirmed
- contradiction_present
- market_reaction_confirmed
- high_authority_source_present

## 17.2 Scheduled release state machine

```text
planned
→ pre_release
→ released
→ reaction_window
→ revised_or_followup
→ closed
```

## 17.3 핵심 점수

### Hotness
얼마나 뜨거운가
- article velocity
- novelty
- source diversity
- authority
- market reaction
- cross-track spillover

### Confidence
얼마나 믿을 만한가
- source credibility
- corroboration
- official confirmation
- extraction confidence
- contradiction penalty

### Actionability
지금 봐야 하는가
- track relevance
- exposure overlap
- upcoming catalysts
- user role / lens

### Disagreement
이야기가 갈리는가
- cross-source stance divergence
- official vs media mismatch
- analyst note conflict

## 17.4 UX와 점수의 연결
사용자에게는 raw score를 그대로 던지지 않는다.

대신:
- Hotness → `Heating / Stable / Cooling`
- Confidence → `Low / Medium / High`
- Disagreement → `Consensus / Mixed / Contested`
- Actionability → `FYI / Watch / Act`

처럼 **의미 있는 상태 언어**로 번역한다.

---

# 18. UI/UX 상세 스펙: 실제 화면은 이렇게 간다

## 18.1 Home / My Tracks (wireframe concept)

```text
┌──────────────────────────────────────────────────────────────┐
│ My Tracks                                                   │
│ Filters: [All] [Scheduled] [Policy] [Breaking] [Themes]    │
│ Lens: [Economist] [PM] [Risk] [Research]                   │
├──────────────────────────────────────────────────────────────┤
│ Needs Attention                                             │
│ 1. US Inflation        Heating  High Conf  Why: CPI release │
│    What changed: official data confirmed upside pressure    │
│    What to watch: Powell speech in 4h                       │
│                                                            │
│ 2. Taiwan Shipping     Active   Medium Conf  Why: route hit │
│    What changed: 3 new corroborating sources                │
│    What to watch: insurer statements                        │
├──────────────────────────────────────────────────────────────┤
│ Scheduled Soon | Heating Up | Watchlist Pressure | Handoffs │
└──────────────────────────────────────────────────────────────┘
```

### UX 의도
- article feed를 없애고 **attention board**로 바꾼다
- 사용자는 먼저 “문제”를 본다
- `why this surfaced`가 항상 보인다

## 18.2 Track Detail (generic shell)

```text
┌──────────────────────────────────────────────────────────────┐
│ US Inflation | Slow-burn Theme | Heating | High Confidence  │
│ What changed: Official CPI release confirmed prior concerns │
│ Why it matters: Delays expected easing path                 │
│ What to watch: Powell speech / 2Y yield / next PPI          │
├──────────────────────────────────────────────────────────────┤
│ State timeline                                               │
│ candidate → corroborating → active → heating                │
├─────────────────────┬────────────────────────────────────────┤
│ Mode-specific area  │ Evidence Drawer                        │
│ Story lanes         │ support / contradictions / sources     │
│ Heatline            │ click any sentence to open spans       │
├─────────────────────┴────────────────────────────────────────┤
│ Memory Lane | Similar episodes | Notes | Share snapshot      │
└──────────────────────────────────────────────────────────────┘
```

## 18.3 Scheduled Release Mode Detail

```text
┌──────────────────────────────────────────────────────────────┐
│ US CPI | Released 08:30 ET | Surprise: +0.3 vs consensus    │
├──────────────────────────────────────────────────────────────┤
│ Actual 3.4 | Expected 3.1 | Previous 3.0 | Revised? No      │
│ Countdown done | Market reaction strip: UST2Y / DXY / SPX   │
├──────────────────────────────────────────────────────────────┤
│ Drivers: shelter↑ services↑ goods flat                      │
│ Official release snippets | First-wave coverage             │
│ Past 6 releases mini timeline                               │
└──────────────────────────────────────────────────────────────┘
```

## 18.4 Policy Mode Detail

```text
┌──────────────────────────────────────────────────────────────┐
│ Fed Speech | Hawkish Shift vs prior speech                  │
├──────────────────────────────────────────────────────────────┤
│ Added phrases: "higher for longer", "inflation persistence" │
│ Removed phrases: "balanced risks"                           │
│ Theme chips: inflation / labor / financial conditions       │
│ Quote cards with evidence spans                             │
│ Compare against previous meeting / speaker history          │
└──────────────────────────────────────────────────────────────┘
```

## 18.5 Breaking Shock Mode Detail

```text
┌──────────────────────────────────────────────────────────────┐
│ Taiwan Shipping Disruption | Corroborated | Geo overlap     │
├──────────────────────────────────────────────────────────────┤
│ Confidence ladder: rumor → corroborated → official          │
│ Map / route view / nearby assets                            │
│ Impact cone: ports / shippers / semis / insurers            │
│ Contradictions: 2 conflicting reports                       │
│ Latest verified change + next expected confirmation         │
└──────────────────────────────────────────────────────────────┘
```

## 18.6 Watchlist / Exposure Mode Detail

```text
┌──────────────────────────────────────────────────────────────┐
│ Semiconductor Watchlist                                     │
├──────────────────────────────────────────────────────────────┤
│ Entity x Driver Matrix                                      │
│           Rates  FX  Supply Chain  Geopolitics  Regulation  │
│ TSMC       Low   Med     High          High         Med      │
│ ASML       Low   Low     Med           Med          High     │
│ NVDA       Med   Low     Low           Med          Med      │
├──────────────────────────────────────────────────────────────┤
│ Upcoming triggers | Top affecting tracks | Shared notes     │
└──────────────────────────────────────────────────────────────┘
```

---

# 19. 왜 이 UX가 기존 툴 대비 더 좋을 가능성이 있나

## 19.1 검색 UX가 아니라 작업 UX를 중심으로 설계했다
기존 제품들이 강한 분야는 search, dashboard, watchlist, alerts, summaries다. [M1][M2][M5][M11][M14]  
우리는 그 위에 한 단계 더 올라가서 **사용자가 문제를 추적하는 실제 흐름**을 product 객체로 만든다.

## 19.2 사건 타입에 맞는 surface를 준다
- 일정형은 calendar / countdown
- 정책형은 language diff
- 실시간 충격은 verification + geo
- 느린 theme는 timeline lanes
- watchlist는 matrix

이건 단순 UI 다양화가 아니라 **cognitive load를 줄이는 UX**다.

## 19.3 alert를 줄이고 의미를 높인다
state-change alert는 article alert보다 피로를 줄이고,  
사용자는 “왜 지금 이게 중요해졌는지”를 더 빨리 이해할 수 있다. [P2][P3]

## 19.4 trust-building을 제품 기본으로 넣는다
evidence drawer, support/contradiction 분리, progressive disclosure는  
AI summary에 대한 신뢰를 높이는 핵심 메커니즘이다. [P4]

## 19.5 memory와 handoff를 넣는다
뉴스 툴이 아니라 **team intelligence system**이 되려면,  
현재 상황뿐 아니라 지난 판단과 과거 유사 사례가 이어져야 한다.

---

# 20. Reliability / governance / review

## 20.1 High-impact track는 human review queue로
아래는 analyst review를 거치게 한다.
- confidence low
- contradiction high
- geopolitical / sanctions / regulatory critical stories
- customer-facing briefings

## 20.2 Auditability
- 모든 summary revision 저장
- source/evidence link 저장
- state transition reason 저장
- 누가 mute/snooze/escalate 했는지 로그 저장

## 20.3 Failure modes
### 실패 1. duplicate flood
해결:
- canonical hash
- similarity collapse
- story-level dedupe

### 실패 2. over-alerting
해결:
- state-change alert only
- suppression windows
- digest mode

### 실패 3. AI가 사실과 추론을 섞음
해결:
- support_level 필수
- verifier agent
- unsupported output 차단

### 실패 4. mode misclassification
해결:
- auto-suggest + manual override
- track admin panel에서 mode 변경 가능

---

# 21. Success metrics: UX를 어떻게 검증할 것인가

## 21.1 Product metrics
- active tracks per user
- repeat open rate of tracks
- track creation to first useful insight 시간
- alert open rate
- alert dismiss / mute rate
- snapshot / briefing share rate

## 21.2 UX quality metrics
- **Time to orient**: alert open 후 핵심 상황 파악까지 걸린 시간
- **Article clicks per resolved question**: 질문 하나 해결하는 데 몇 개 문서를 열었는지
- **Evidence click-through**: 고위험 story에서 근거 확인 비율
- **Why this surfaced comprehension**: 왜 surfaced됐는지 이해했는지
- **Handoff success rate**: 다른 사람이 note/snapshot만으로 이어서 이해 가능한지

## 21.3 Model metrics
- event extraction accuracy
- story clustering purity
- unsupported claim rate
- evidence coverage rate
- contradiction detection precision
- alert precision@k

---

# 22. MVP → Beta → Production rollout

## 22.1 Phase 1: Low-cost MVP (6~8주)
범위:
- US macro 중심
- source: Fed RSS + BLS + ECB 일부 + GDELT
- modes: Scheduled Release / Policy / Slow-Burn
- lenses: Economist / PM only
- UI:
  - My Tracks
  - Track Detail
  - Evidence Drawer
  - Daily Digest

아키텍처:
- Next.js
- FastAPI
- Redis
- Postgres + pgvector
- SSE
- `gpt-5-mini` + `gpt-5-nano`

목표:
- 발표/기사가 뜨고 1~5분 내 반영
- 같은 theme를 story로 묶기
- 3문장 요약 + evidence 연결
- alert flood 없이 meaningful update 제공

## 22.2 Phase 2: Production Beta (8~16주)
추가:
- Breaking Shock Mode
- Watchlist / Exposure Mode
- Handoff notes
- Snapshot / briefing export
- source lanes
- contradiction tab
- role-based module ordering

아키텍처 추가:
- object storage
- observability stack
- improved retry / dead-letter handling
- team workspace / RBAC

## 22.3 Phase 3: Full Production
추가:
- premium news / Event Registry 등 paid enrichment
- internal note connectors
- optional Neo4j read model
- advanced memory lane
- cross-track synthesis
- mobile / email / Slack digests
- enterprise governance / audit / SSO

---

# 23. Hard decisions / Hard no’s

## 23.1 처음부터 하지 않을 것
- 전 단계 agent swarm
- Neo4j를 source of truth로 두기
- separate vector DB + graph DB + OLAP를 모두 day-1에 넣기
- article-level alert flood
- one universal feed UI
- unsupported long-form AI opinions
- full macro forecasting platform처럼 포장하기

## 23.2 반드시 할 것
- Track-first model
- mode-aware UX
- JSON contracts
- Postgres-centered architecture
- evidence-first summaries
- state-change alerts
- handoff / memory design

---

# 24. 최종 추천안 (실행용)

## 24.1 지금 바로 확정해도 되는 것
1. 제품의 중심 객체는 `Track`
2. 차별화 포인트는 **tracking UX**
3. real-time MVP는 공식 소스 + GDELT로 가능
4. infra는 Hetzner 위 `FastAPI + Next.js + Redis + Postgres + pgvector`
5. LLM은 `gpt-5-mini` 중심, `gpt-5-nano` 보조
6. agent 간 통신은 JSON
7. graph DB는 나중
8. 화면은 기사 feed보다 `My Tracks → Track Detail → Evidence Drawer`
9. alert는 state change 기준
10. UX는 `Mode + Lens` 조합으로 설계

## 24.2 네 제품의 제일 중요한 한 줄
> **이 제품은 “뉴스를 많이 보여주는 툴”이 아니라, “사건 유형에 맞는 tracking surface로 변화·의미·근거를 빠르게 이해시키는 툴”이어야 한다.**

---

# 25. Reference notes

## Market / product docs
- [M1] AlphaSense Smart Summaries — https://www.alpha-sense.com/platform/smart-summaries/
- [M2] AlphaSense Help Center, Maximizing Your Monitoring Tools in AlphaSense — https://help.alpha-sense.com/hc/en-us/articles/41815509396371-Maximizing-Your-Monitoring-Tools-in-AlphaSense
- [M3] AlphaSense Help Center, Leveraging and Customizing Your Dashboard — https://help.alpha-sense.com/hc/en-us/articles/41809206884243-Leveraging-and-Customizing-Your-Dashboard
- [M4] AlphaSense Help Center, Saving Searches and Building Alerts — https://help.alpha-sense.com/hc/en-us/articles/41815267178899-Saving-Searches-and-Building-Alerts
- [M5] LSEG Workspace / personalized insights and analytics — https://www.lseg.com/en/data-analytics/products/workspace
- [M6] LSEG Company Events Coverage / customized calendar / ADVEV — https://www.lseg.com/en/data-analytics/financial-data/company-data/company-events-coverage-data
- [M7] LSEG Watchlist Pulse Quick Reference Card — https://video.training.refinitiv.com/elearning_video/Documents/Eikon_QRC/Eikon%20Quick%20Reference%20Card%20-%20Watchlist%20Pulse%20App.pdf
- [M8] LSEG Portfolio Management / Watchlist Pulse overview — https://www.lseg.com/en/data-analytics/asset-management-solutions/portfolio-management
- [M9] Dataminr Geovisualization — https://www.dataminr.com/pulse/corporate-security/geovisualization/
- [M10] Dataminr product/press material on custom views and geovisualization — https://www.dataminr.com/press/dataminr-bolsters-corporate-product-offering-with-new-capabilities/
- [M11] Event Registry blog, New to Event Registry? — https://eventregistry.org/blog/new-to-event-registry-/
- [M12] NewsAPI.ai / Event Registry News API — https://eventregistry.org/news_api
- [M13] RavenPack News Analytics — https://www.ravenpack.com/products/edge/data/news-analytics
- [M14] S&P Capital IQ Pro — https://www.spglobal.com/market-intelligence/en/solutions/products/sp-capital-iq-pro
- [M15] S&P Global press release on Multi-Document ChatIQ / Document Intelligence — https://press.spglobal.com/2025-10-22-S-P-Global-Redefines-Financial-Insights-with-New-AI-Powered-Multi-Document-Research-and-Analysis-Tool-in-Capital-IQ-Pro-ChatIQ
- [M16] Federal Reserve RSS feeds — https://www.federalreserve.gov/feeds/feeds.htm
- [M17] ECB RSS feeds — https://www.ecb.europa.eu/home/html/rss.en.html
- [M18] BLS release calendar — https://www.bls.gov/schedule/
- [M19] GDELT data / free and open — https://www.gdeltproject.org/data.html
- [M20] OpenAI GPT-5 nano model page — https://developers.openai.com/api/docs/models/gpt-5-nano
- [M21] OpenAI reasoning models guide — https://developers.openai.com/api/docs/guides/reasoning/
- [M22] OpenAI GPT-5 mini model page — https://developers.openai.com/api/docs/models/gpt-5-mini
- [M23] OpenAI pricing page — https://developers.openai.com/api/docs/pricing/
- [M24] OpenAI embeddings API reference / embedding models — https://platform.openai.com/docs/api-reference/embeddings/create

## Research / papers / design evidence
- [P1] newsLens: building and visualizing long-ranging news stories — https://aclanthology.org/W17-2701/
- [P2] Alert Fatigue in Security Operations Centres — https://dl.acm.org/doi/10.1145/3723158
- [P3] Reuters Institute Digital News Report 2025 — https://reutersinstitute.politics.ox.ac.uk/digital-news-report/2025
- [P4] Surfacing AI Explainability in Enterprise Product Visualizations — https://dl.acm.org/doi/10.1145/3544549.3573867
- [P5] Data Storytelling in Data Visualisation: Does it Enhance the Effectiveness and Efficiency of Information Comprehension? — https://dl.acm.org/doi/10.1145/3613904.3643022
- [P6] Future Timelines: Extraction and Visualization of Entity-Centric Future Event Information from News — https://dl.acm.org/doi/10.1145/3616855.3635693
- [P7] Narrative Trails: A Method for Coherent Storyline Extraction in Large Text Corpora — https://arxiv.org/html/2503.15681v1

---

# 26. 다음 문서로 바로 이어질 수 있는 것
이 문서 다음 단계로 바로 만들 수 있는 산출물:
1. `system_architecture.md`
2. `db_schema.sql`
3. `agent_json_schemas.md`
4. `tracking_ux_wireframes.md`
5. `mvp_build_plan_8_weeks.md`
