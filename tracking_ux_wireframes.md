# Tracking UX Wireframes
## Macro Economics Tracker — production UX spec centered on tracking
- Version: v1
- Updated: 2026-03-06
- Companion docs:
  - `macro_economics_tracker_prd.md`
  - `db_schema.sql`
- Focus: **UI보다 UX**. 즉 화면 생김새보다, 사용자가 어떻게 `추적`하고 `이해`하고 `행동`하는지에 집중한다.

---

# 1. 이 문서의 목적

이 문서는 **기존 뉴스/리서치 툴의 한계가 “검색과 알림은 있는데 tracking 경험은 약하다”**는 전제에서 출발한다.

핵심 질문은 세 가지다.

1. 사용자는 지금 **무슨 이슈가 바뀌었는지** 어떻게 알아차리는가?
2. 그 변화가 **왜 중요한지** 어떻게 빨리 이해하는가?
3. 그 판단을 **어떤 근거로 믿을지** 어떻게 검증하는가?

이 제품은 여기서 아래 6가지 UX 원칙으로 차별화한다.

1. **Track-first**: 검색 결과가 아니라 `Track`가 기본 단위다.
2. **Mode-aware**: 사건 종류마다 다른 추적 화면을 준다.
3. **State-change first**: 기사 알림이 아니라 상태 변화 알림을 준다.
4. **Evidence-first**: 모든 요약은 바로 근거를 열어볼 수 있어야 한다.
5. **Memory-aware**: “지금”만 보여주지 말고 “무엇이 달라졌는지”를 비교해서 보여준다.
6. **Action-oriented**: 사용자는 기사 리스트보다 `What changed / Why it matters / What to watch next`를 먼저 본다.

---

# 2. UX North Star

> **A user should understand a developing macro story in under 20 seconds, verify it in under 2 clicks, and decide what to watch next without opening 10 articles.**

이 문장을 만족하지 못하면 tracking UX가 아니다.

---

# 3. 핵심 개념

## 3.1 Track
사용자가 지속적으로 감시하고 싶은 문제 단위.

예:
- US Inflation
- Fed 2026 easing path
- China property stress
- Taiwan Strait tension
- Oil supply disruption
- EUR/USD drivers

Track는 단순 키워드 검색이 아니라 아래를 포함하는 **상태 있는 monitoring object**다.
- entities
- themes
- regions
- assets
- mode
- alert policy
- evidence strictness
- memory window
- owner / team / notes

## 3.2 Story
Track 안에 묶이는 구체적 이야기 묶음.

예:
- “US CPI came in hotter than expected”
- “Fed speakers pushed back on early cuts”
- “Brent crude jumped after shipping disruption”

## 3.3 Episode
Story의 의미 있는 상태 변화 단위.

예:
- rumor 등장
- official release 공개
- central bank speaker 발언
- market reaction 확인
- contradiction 발생
- issue cooling

**핵심 UX 차별화는 기사(article) 단위가 아니라 `episode` 단위로 추적하게 만드는 것**이다.

## 3.4 Evidence
AI가 말한 문장을 뒷받침하는 정확한 근거 span.

사용자는 아래 흐름으로 내려갈 수 있어야 한다.

`track summary -> episode -> sentence -> evidence span -> source document`

---

# 4. 누구를 위한 UX인가

## 4.1 Primary user
- macro/market analyst
- PM/투자팀
- risk/intelligence analyst
- research associate

## 4.2 Secondary user
- executive / desk head
- junior analyst
- CS student demo evaluator

## 4.3 UX에서 중요한 차이
전문가도 결국 바쁜 사람이다. 그래서 UX는 아래 두 층을 동시에 만족해야 한다.

### Layer A: 20초 이해
- 아주 짧은 narrative
- 상태 변화만
- 우선순위가 정렬된 inbox

### Layer B: 2분 검증
- evidence span
- source diversity
- official vs media 구분
- contradiction 여부

---

# 5. 차별화 포인트: 같은 뉴스 추적이어도 UX는 다르게 해야 한다

기존 도구들은 watchlist / dashboard / search / alerts는 강하지만, 서로 다른 사건 유형을 같은 feed나 같은 리스트로 처리하는 경우가 많다.

이 제품은 **Track Mode**를 핵심 UX 축으로 둔다.

## 5.1 Track Mode taxonomy

| Mode | 대표 예시 | 사용자의 핵심 질문 | 기본 화면 |
|---|---|---|---|
| Scheduled Release | CPI, NFP, GDP, PMI, central bank meeting | 발표 전/후로 뭐가 달라졌나? | countdown + release board + reaction lanes |
| Policy Communication | speech, minutes, interview, official guidance | 톤이 바뀌었나? 누가 더 hawkish/dovish인가? | quote diff + speaker map + stance timeline |
| Breaking Shock | sanctions, war escalation, cyberattack, earthquake, shipping disruption | 지금 얼마나 확실한가? 어디까지 번지나? | uncertainty ladder + geo/exposure map + episode feed |
| Slow-burn Theme | China property, deglobalization, AI capex, inflation persistence | 조용히 커지는 장기 흐름인가? 전환점은 뭐였나? | theme river + memory snapshots + turning points |
| Watchlist / Exposure | portfolio, sector, FX book, rates book | 내 관심 자산/노출에 뭐가 중요해졌나? | driver × exposure matrix + ranked impact list |

### 가장 중요한 설계 원칙
**Mode가 바뀌면 카드 배치만 바꾸는 게 아니라, 질문 구조와 interaction model 자체가 바뀌어야 한다.**

---

# 6. Mode별 상태기계(State Machine)

이게 tracking UX의 핵심이다. 모든 story에 하나의 generic status만 주면 차별화가 사라진다.

## 6.1 Scheduled Release 상태기계
`upcoming -> release out -> first interpretation -> market repricing -> follow-through -> cooling`

UX implication:
- 발표 전엔 countdown과 prior snapshot이 중요
- 발표 직후엔 actual vs expected와 official source가 중요
- 몇 분 뒤엔 market reaction lane이 중요
- 몇 시간 뒤엔 follow-up commentary가 중요

## 6.2 Policy Communication 상태기계
`scheduled -> statement/speech delivered -> stance interpreted -> follow-up speakers -> market confirmation/challenge -> cooling`

UX implication:
- quote diff가 핵심
- speaker별 stance 변화를 보여줘야 함
- “이번 발언이 지난 회의/연설과 무엇이 다른가”를 바로 보여줘야 함

## 6.3 Breaking Shock 상태기계
`rumor -> corroborated -> official confirmation -> spread / secondary effects -> stabilization / resolution`

UX implication:
- 초기엔 신뢰도와 corroboration이 제일 중요
- 이후엔 geography / exposure / secondary impact가 중요
- 완화 단계에선 “무엇이 해소되었는가”를 보여줘야 함

## 6.4 Slow-burn Theme 상태기계
`weak signals -> emerging pattern -> sustained theme -> regime shift candidate -> normalization`

UX implication:
- 기사 수보다 narrative drift가 중요
- turning point와 recurrence를 보여줘야 함
- 7일/30일/90일 비교가 핵심

## 6.5 Watchlist / Exposure 상태기계
`new risk/opportunity -> exposure identified -> priority ranked -> action taken / note added -> monitored -> cleared/escalated`

UX implication:
- 기사보다 “내 리스트에 얼마나 중요한가”가 먼저여야 함
- matrix와 ranked impact list가 필요

---

# 7. Information Architecture

```text
Home
├── Inbox (state-change feed)
├── Tracks
│   ├── All Tracks
│   ├── My Tracks
│   ├── Team Tracks
│   └── Create Track
├── Track Detail
│   ├── Overview
│   ├── Storyline
│   ├── Evidence
│   ├── Calendar / Map / River / Matrix (mode-specific)
│   ├── Notes & Memory
│   └── Alert Rules
├── Stories
│   ├── Story Detail
│   └── Compare Stories
├── Calendar
├── Explore
└── Settings
```

## 중요한 UX 결정
- `Home`는 기사 feed가 아니라 **Inbox + Track health** 중심
- `Explore`는 검색용
- **주 업무는 Track Detail에서 일어난다**

---

# 8. Global UX primitives

## 8.1 Top Summary Frame
모든 Track 상세 상단은 아래 3문장 구조를 유지한다.
- **What changed**
- **Why it matters**
- **What to watch next**

이건 어떤 mode에서도 바뀌지 않는다.

## 8.2 Memory Ribbon
상단 요약 바로 아래에 항상 비교 기준을 둔다.

예:
- vs previous CPI release
- vs last FOMC meeting
- vs 7 days ago
- vs first alert
- vs last portfolio snapshot

Memory Ribbon은 단순 히스토리가 아니라 **“무엇과 비교 중인지”를 명시하는 UX 장치**다.

## 8.3 Evidence Drawer
모든 생성 문장에 hover/click로 evidence drawer가 열린다.

Drawer 안에는 최소한 아래가 보인다.
- supporting spans
- source type (official / newswire / publisher / internal)
- source diversity
- support verdict (`supported / inferred / weak / contradicted`)

## 8.4 Confidence + Contradiction strip
상단 summary 옆에 막대 2개를 둔다.
- confidence
- contradiction

같은 이슈라도 정보가 엇갈리면 **중요하지만 불확실함**을 바로 전달해야 한다.

## 8.5 Episode Inbox
기사 목록 대신 episode 목록.

카드 예시:
- Official release posted
- Market reaction confirmed
- New contradictory report
- Story cooled; no fresh official confirmation in 18h

## 8.6 Source Mix pill
각 story/episode 카드에 source mix를 붙인다.

예:
- `official + 4 wires + 2 publishers`
- `media only`
- `single-source only`

이건 trust calibration에 중요하다.

---

# 9. Global layout wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Left Nav            │ Top Bar: search / filters / time range / compare     │
├─────────────────────┬──────────────────────────────────────┬─────────────────┤
│ Track List / Inbox  │ Main Canvas                          │ Right Rail      │
│                     │                                      │                 │
│ - My Tracks         │ [Top Summary Frame]                  │ [Track Health]  │
│ - Team Tracks       │ What changed / Why / Watch next      │ confidence      │
│ - Alerts            │ [Memory Ribbon]                      │ contradiction   │
│ - Saved Views       │                                      │ officiality     │
│                     │ [Mode-specific Primary Surface]      │                 │
│                     │                                      │ [Open Questions]│
│                     │ [Episode Inbox / Storyline]          │ [Linked Tracks] │
│                     │                                      │ [Notes]         │
├─────────────────────┴──────────────────────────────────────┴─────────────────┤
│ Bottom Slide-up Drawer: Evidence / Source / Claim lineage                    │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

# 10. Home / Inbox UX

## 목적
사용자가 제품에 들어오자마자 보는 것은 “최신 기사”가 아니라 **내가 봐야 할 변화**여야 한다.

## 홈 화면 구조

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ TODAY'S CHANGES                                                             │
│ 1. US Inflation [Scheduled Release] changed state: release out              │
│ 2. Fed Easing Path [Policy] contradiction increased                         │
│ 3. Red Sea Shipping [Breaking Shock] official confirmation appeared         │
│ 4. China Property [Slow-burn] sustained theme for 14 days                  │
├──────────────────────────────────────────────────────────────────────────────┤
│ My Tracks (health view)      │ Upcoming critical events                     │
│ - health score               │ - CPI in 01:12:20                            │
│ - unread state changes       │ - ECB speech in 03:45:00                     │
│ - stale tracks               │ - payrolls tomorrow                          │
├──────────────────────────────────────────────────────────────────────────────┤
│ Recommended attention now                                                 │
│ - 3 tracks with high impact + high uncertainty                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## UX 의도
- inbox는 `importance x uncertainty x freshness` 기준 정렬
- 아직 변화가 없는 track은 조용해야 함
- alert fatigue를 줄이기 위해 `many articles`를 직접 강조하지 않음

---

# 11. Track creation UX

## 핵심
사용자에게 복잡한 query builder를 먼저 강요하지 않는다.

## 4-step wizard

### Step 1. 무엇을 추적하나?
- free text 입력: “US inflation”
- 추천 mode 자동 제안
- 관련 entities/themes 자동 추출

### Step 2. 어떤 tracking mode인가?
- scheduled release
- policy communication
- breaking shock
- slow-burn theme
- watchlist / exposure

### Step 3. 어떤 것에 민감한가?
- official only 우선
- media + official
- contradiction에 민감
- market reaction까지 보려는지
- immediate / digest / quiet mode

### Step 4. 비교 기준은 무엇인가?
- previous release
- last 7d / 30d
- previous meeting
- first alert
- watchlist snapshot

## Track creation wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Create Track                                                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│ [1] Describe in plain language                                               │
│     "Track Fed easing expectations and inflation surprises"                 │
│                                                                              │
│ Suggested entities: Fed, CPI, US 2Y, USD                                     │
│ Suggested mode: Policy Communication + Scheduled Release                     │
│                                                                              │
│ [2] Choose dominant mode                                                     │
│  (•) Policy Communication  ( ) Scheduled Release  ( ) Breaking Shock        │
│                                                                              │
│ [3] Alert sensitivity                                                        │
│  [x] Official confirmation   [x] Contradiction   [ ] Social-only signals     │
│                                                                              │
│ [4] Memory baseline                                                          │
│  Compare against: [Last FOMC] [Previous CPI] [7d]                            │
│                                                                              │
│                          [Create Track]                                       │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

# 12. Mode-specific UX

## 12.1 Scheduled Release Mode

### 언제 쓰는가
- CPI, PPI, payrolls, GDP, PMI, retail sales
- central bank meeting statements
- official calendar-driven events

### 사용자 질문
- 발표 전: 시장은 뭘 기대하나?
- 발표 직후: 실제 수치가 뭐였나?
- 그 직후: 왜 surprise인가?
- 몇 분 뒤: 시장이 어떻게 반응했나?

### 핵심 UX 구조
1. **Countdown + scenario prep**
2. **Actual vs Expected board**
3. **What changed vs prior release**
4. **Reaction lane**
5. **Follow-up commentary**

### Desktop wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Track: US Inflation [Scheduled Release]                                     │
│ What changed: CPI came in above consensus                                   │
│ Why it matters: pushes back early easing expectations                        │
│ What to watch: Fed speakers and front-end rates                             │
├──────────────────────────────────────────────────────────────────────────────┤
│ Memory Ribbon: vs previous CPI | vs consensus | vs 7d narrative             │
├──────────────────────────────┬───────────────────────────────────────────────┤
│ Countdown / Release Card     │ Release Board                                 │
│ - next release / just out    │ Headline CPI: 3.4% vs 3.2% exp               │
│ - official source link       │ Core CPI: 3.6% vs 3.5% exp                   │
│ - prep checklist             │ Surprise direction: hotter                    │
│                              │ Summary confidence / evidence                 │
├──────────────────────────────┴───────────────────────────────────────────────┤
│ Reaction Lanes                                                               │
│ Official release | News interpretation | Rates | USD | Equities | Notes      │
│ 08:30 official   | 08:31 Reuters       | 08:32 UST2Y | 08:34 DXY | ...       │
├──────────────────────────────────────────────────────────────────────────────┤
│ Episode Inbox                                                                 │
│ - official release posted                                                     │
│ - first media interpretation                                                  │
│ - market repricing confirmed                                                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### UX differentiation point
기존 캘린더형 도구가 “무슨 일정이 있나”를 잘 보여준다면, 여기서는 **이 일정이 release 전후로 어떻게 state를 바꿨는지**를 더 잘 보여준다.

### Interaction rules
- release 전 24h: prep mode 기본
- release 후 30m: reaction mode 기본
- 하루 후: compare to previous release mode 기본

---

## 12.2 Policy Communication Mode

### 언제 쓰는가
- Fed/ECB/BoJ/BoE speeches
- FOMC minutes
- interviews / official Q&A
- guidance shifts

### 사용자 질문
- 이번 발언의 톤이 과거보다 바뀌었나?
- 누가 더 hawkish / dovish한가?
- 시장이 그 톤 변화를 인정했나?

### 핵심 UX 구조
1. **Quote diff**
2. **Speaker stance map**
3. **Policy narrative timeline**
4. **Market confirmation vs challenge**

### Desktop wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Track: Fed Easing Path [Policy Communication]                               │
│ What changed: recent speakers pushed back on near-term cuts                 │
│ Why it matters: rate-cut timing repricing risk                              │
│ What to watch: next Chair remarks and CPI                                   │
├──────────────────────────────────────────────────────────────────────────────┤
│ Memory Ribbon: vs last FOMC | vs last Chair speech | vs last 14 days        │
├──────────────────────────────┬───────────────────────────────────────────────┤
│ Quote Diff                   │ Speaker Map                                   │
│ Previous wording             │ hawkish <-------> dovish                      │
│ New wording                  │ Waller  Bowman  Chair  Williams               │
│ Highlighted shift phrases    │ shift since last appearance                   │
├──────────────────────────────┴───────────────────────────────────────────────┤
│ Policy Timeline                                                               │
│ Meeting -> minutes -> speeches -> media narrative -> rates repricing         │
├──────────────────────────────────────────────────────────────────────────────┤
│ Evidence Drawer Triggered by quote click                                     │
│ exact span / source / support verdict                                        │
└──────────────────────────────────────────────────────────────────────────────┘
```

### UX differentiation point
이 mode에서는 기사 수보다 **문구 변화**가 중요하다. 그래서 카드보다 `quote diff`가 전면에 나와야 한다.

### Interaction rules
- quote hover -> previous comparable quote overlay
- click stance chip -> speaker timeline only filter
- contradiction chip -> open articles/spans arguing the opposite

---

## 12.3 Breaking Shock Mode

### 언제 쓰는가
- sanctions
- war escalation
- cyberattack
- natural disaster
- shipping route disruption
- plant fire / supply shock

### 사용자 질문
- 지금 이게 사실로 어느 정도 확인됐나?
- 영향 범위가 어디까지 확장되나?
- secondary effect가 있는가?

### 핵심 UX 구조
1. **Uncertainty ladder**
2. **Geo / blast radius / exposure**
3. **Official confirmation tracker**
4. **Secondary effect chain**

### Desktop wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Track: Red Sea Shipping Disruption [Breaking Shock]                         │
│ What changed: official confirmation now present from multiple sources       │
│ Why it matters: oil/logistics risk spilling into broader inflation concerns │
│ What to watch: shipping reroutes, insurance, crude, freight                │
├──────────────────────────────────────────────────────────────────────────────┤
│ Confidence / Contradiction / Source Mix                                     │
├──────────────────────────────┬───────────────────────────────────────────────┤
│ Uncertainty Ladder           │ Geo + Exposure                                │
│ Rumor                        │ map / route / ports / affected assets         │
│ Corroborated                 │                                               │
│ Official confirmed           │                                               │
│ Secondary effects            │                                               │
├──────────────────────────────┴───────────────────────────────────────────────┤
│ Contagion Chain                                                              │
│ incident -> route disruption -> freight -> oil -> inflation narrative        │
├──────────────────────────────────────────────────────────────────────────────┤
│ Episode Inbox                                                                 │
│ - first local reports                                                         │
│ - wire corroboration                                                          │
│ - official statement                                                          │
│ - market spillover                                                            │
└──────────────────────────────────────────────────────────────────────────────┘
```

### UX differentiation point
초기 breaking event에서는 “중요해 보인다”와 “아직 불확실하다”를 동시에 전달해야 한다. 그래서 색상 경고보다 **uncertainty ladder**가 먼저다.

### Interaction rules
- click any map node -> related story subset only
- click contagion edge -> evidence chain open
- official confirmation badge always sticky

---

## 12.4 Slow-burn Theme Mode

### 언제 쓰는가
- China property stress
- inflation persistence
- deglobalization
- secular AI capex
- productivity slowdown

### 사용자 질문
- 이게 일시적 noise인가, 지속되는 테마인가?
- 전환점은 언제였나?
- 요즘 narrative가 어떻게 drift하고 있나?

### 핵심 UX 구조
1. **Theme river / trend bands**
2. **Turning points**
3. **Memory snapshots**
4. **Sub-theme decomposition**

### Desktop wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Track: China Property Stress [Slow-burn Theme]                              │
│ What changed: theme intensity has persisted for 21 days                     │
│ Why it matters: growth and credit concerns remain unresolved                │
│ What to watch: policy response, developers, local financing                 │
├──────────────────────────────────────────────────────────────────────────────┤
│ Memory Ribbon: vs 7d | vs 30d | vs first signal | vs previous policy push   │
├──────────────────────────────┬───────────────────────────────────────────────┤
│ Theme River                  │ Turning Points                                │
│ subtheme volume + tone       │ episode markers + narrative shifts            │
│ property / credit / policy   │                                               │
├──────────────────────────────┴───────────────────────────────────────────────┤
│ Narrative Drift Panel                                                         │
│ - what became more prominent                                                  │
│ - what faded                                                                  │
│ - what new entities entered the story                                         │
├──────────────────────────────────────────────────────────────────────────────┤
│ Story Memory Snapshots                                                        │
│ [7d ago] [30d ago] [last policy intervention]                                 │
└──────────────────────────────────────────────────────────────────────────────┘
```

### UX differentiation point
느린 테마는 실시간 속도보다 **누적 의미와 전환점**이 중요하다. 기사 feed는 여기서 거의 무가치하다.

### Interaction rules
- scrub time range -> summary rewrites itself for chosen window
- click turning point -> compare before/after evidence
- default view = 30d, not 24h

---

## 12.5 Watchlist / Exposure Mode

### 언제 쓰는가
- 내 포트폴리오/섹터/국가 익스포저 추적
- 특정 종목/통화/금리북에 어떤 macro driver가 중요한지 보기

### 사용자 질문
- 내 관심 대상 중 뭐가 가장 위험/기회가 커졌나?
- 어떤 macro driver가 어떤 asset을 밀고 있나?
- 어디부터 봐야 하나?

### 핵심 UX 구조
1. **Driver × Exposure matrix**
2. **Impact-ranked list**
3. **Entity exposure chains**
4. **Action queue**

### Desktop wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Track: FX Book Risk [Watchlist / Exposure]                                  │
│ What changed: USD-sensitive exposures moved to top priority                 │
│ Why it matters: stronger inflation narrative delays easing expectations     │
│ What to watch: DXY, UST2Y, ECB/Fed communication                            │
├──────────────────────────────────────────────────────────────────────────────┤
│ Driver × Exposure Matrix                                                     │
│                 USD   EURUSD   EM FX   Rates   Growth Equities              │
│ Inflation       High   Med      High    High    Med                          │
│ Fed stance      High   High     Med     High    High                         │
│ Oil shock       Med    Low      High    Med     Med                          │
├──────────────────────────────────────────────────────────────────────────────┤
│ Ranked Impact List                                                           │
│ 1. USD basket        ↑ priority                                              │
│ 2. Front-end rates   ↑ priority                                              │
│ 3. EM FX             watch                                                   │
├──────────────────────────────────────────────────────────────────────────────┤
│ Linked Story Chains                                                           │
│ CPI surprise -> Fed repricing -> USD -> EM FX                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

### UX differentiation point
이 mode에서는 기사 수나 topic volume보다 **내 관심 대상과 연결된 영향도**가 제일 중요하다.

### Interaction rules
- click matrix cell -> show only relevant stories + evidence chain
- allow manual override note: “this exposure matters more to my desk”

---

# 13. Story Detail UX

Track와 Story는 다르다. Track는 장기 monitoring object이고, Story는 그 안의 특정 이슈다.

## Story detail wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Story: US CPI surprise sparks rate repricing                                │
│ State: developing -> confirmed                                              │
│ Linked Tracks: US Inflation / Fed Easing Path / Rates Book                  │
├──────────────────────────────────────────────────────────────────────────────┤
│ Top Summary                                                                  │
│ - what changed                                                               │
│ - why it matters                                                             │
│ - what next                                                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│ Episode Timeline                                                             │
│ [official release] [wire interpretation] [UST2Y spike] [Fed comments]       │
├──────────────────────────────────────────────────────────────────────────────┤
│ Claims & Evidence                                                            │
│ sentence 1 -> supported spans                                                │
│ sentence 2 -> inferred                                                       │
│ sentence 3 -> contradictory evidence exists                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│ Related Entities / Related Stories / Notes                                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

## UX rule
- 사용자는 Story detail에서 **story를 검증**해야 한다.
- Track detail에서는 **우선순위를 정하고 흐름을 이해**해야 한다.

---

# 14. Evidence Drawer UX

이 제품의 trust는 여기서 결정된다.

## Drawer contents
1. selected claim or sentence
2. support verdict
3. exact supporting spans
4. contradicting spans
5. sources ordered by authority
6. “observed fact” vs “model inference” 분리

## Evidence Drawer wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Evidence Drawer                                                               │
├──────────────────────────────────────────────────────────────────────────────┤
│ Selected sentence                                                             │
│ "Fed repricing risk increased after hotter CPI."                            │
│ Verdict: SUPPORTED + partial inference                                        │
├──────────────────────────────────────────────────────────────────────────────┤
│ Observed facts                                                                │
│ - CPI above consensus [official source span]                                  │
│ - UST2Y moved +11bp in 20m [market data span]                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│ Model inference                                                               │
│ - this likely delays cuts                                                     │
├──────────────────────────────────────────────────────────────────────────────┤
│ Contradicting / balancing evidence                                             │
│ - 1 source argues one-off seasonal distortion                                 │
└──────────────────────────────────────────────────────────────────────────────┘
```

## UX rule
절대 “AI says so”가 아니라 “이 span 때문에 그렇게 말했다”가 되어야 한다.

---

# 15. Alert UX

## 문제
기사 단위 alert는 너무 시끄럽다.

## 해결
`state-change alert` 중심으로 재설계한다.

## Alert types
- story_created
- official_confirmation_added
- contradiction_increased
- market_reaction_confirmed
- track_priority_upgraded
- scheduled_event_soon
- scheduled_event_released
- daily_digest

## Notification examples
- `US Inflation: release out. CPI above consensus. 3 supporting sources.`
- `Fed Easing Path: contradiction increased. 2 speakers diverged from prior narrative.`
- `Red Sea Shipping: official confirmation appeared. Exposure to oil/freight tracks updated.`

## Alert Center wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Alert Center                                                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│ [High] US Inflation — scheduled event released                               │
│ [High] Red Sea Shipping — official confirmation                              │
│ [Med] Fed Easing Path — contradiction increased                              │
│ [Low] China Property — no major state change, included in digest             │
└──────────────────────────────────────────────────────────────────────────────┘
```

## UX rules
- 한 story는 같은 reason으로 짧은 시간에 중복 푸시 금지
- article count 증가만으로 알림 보내지 않음
- digest/real-time/quiet mode를 user가 Track별로 다르게 선택 가능

---

# 16. Memory UX

이 제품이 기존 툴과 달라지려면 **“현재 상태”보다 “상태 변화”를 오래 기억하는 제품**이어야 한다.

## 핵심 장치 4개

### 16.1 Snapshot compare
- yesterday vs now
- previous release vs now
- first alert vs now
- last meeting vs now

### 16.2 Turning point markers
긴 테마에서 중요한 분기점 표시.

### 16.3 Analyst note anchors
노트가 특정 story/episode/evidence에 붙는다.

### 16.4 Open questions
“아직 확인되지 않은 것”도 상태로 저장.

## Open questions 예시
- Is the market overreacting?
- Has there been official confirmation?
- Which speakers matter most next?
- Is this spillover broadening to EM FX?

---

# 17. Search UX는 어떻게 달라야 하나

이 제품의 메인은 tracking이지만 search도 필요하다.

## 검색 결과 기본 그룹핑
- Articles
- Stories
- Tracks
- Entities
- Events

## 기본값
**search result default tab = Stories**, not Articles.

## 이유
사용자는 보통 기사 50개보다 “무슨 이야기들이 있나”를 먼저 알고 싶다.

---

# 18. Collaboration UX

## 기본 collaboration objects
- shared track
- shared note
- mention
- decision tag
- pin important episode

## 팀 UX 규칙
- note는 문서 전체가 아니라 story/episode/evidence에 붙여야 함
- track에 “desk perspective”를 덧붙일 수 있어야 함
  - macro desk
  - EM desk
  - rates desk
  - risk desk

---

# 19. Mobile / compact UX

핵심은 축소판 기사 feed가 아니다.

## 모바일에서 보여줄 것
1. what changed
2. why it matters
3. one-tap evidence
4. one-tap follow / mute / digest

## 모바일에서는 숨길 것
- 복잡한 graph
- dense matrix full version
- long evidence trees

---

# 20. Empty / stale / uncertainty states

## Empty state
“아직 중요한 state change가 없습니다. 이 Track는 quiet mode로 전환할 수 있습니다.”

## Stale state
“최근 5일간 새로운 episode가 없습니다. baseline을 30일로 넓혀볼까요?”

## High uncertainty state
“중요도는 높지만 corroboration이 부족합니다. single-source 상태입니다.”

이런 문구가 UX에서 중요하다. 데이터가 부족한 걸 숨기면 안 된다.

---

# 21. Accessibility & usability

## 필수 원칙
- 색만으로 risk/confidence 구분 금지
- confidence/contradiction는 숫자/문구 함께 표기
- keyboard navigation: track, story, evidence drawer 모두 지원
- evidence spans는 복붙 가능해야 함
- dense dashboard에서도 line length 제한

## 권장 단축키
- `g t` : track list
- `g i` : inbox
- `e` : evidence drawer toggle
- `[` `]` : previous/next episode
- `c` : compare baseline change

---

# 22. UX metrics

## Activation
- first track created within first session
- first evidence click within first session

## Core value
- time-to-first-understanding
- evidence open rate
- % alerts opened
- % alerts muted
- story-to-article click ratio
- repeat track visits

## Trust
- unsupported claim rate
- contradiction surfaced before user complaint
- source diversity on top stories

## Noise reduction
- alerts per active user per day
- muted alerts rate
- digest preference adoption

---

# 23. Production UX requirements

## Must-have
- SSE live updates
- optimistic but auditable story updates
- loading skeleton for state transitions
- idempotent notifications
- latency budget visible in internal metrics
- stale badge if latest update is delayed

## Nice-to-have
- compare mode across two tracks
- analyst handoff summary
- weekend digest
- decision journal

---

# 24. Figma-ready component inventory

## Global
- TrackCard
- StoryCard
- EpisodeCard
- SourceMixPill
- ConfidenceStrip
- ContradictionStrip
- MemoryRibbon
- EvidenceDrawer
- WhatChangedPanel
- WhyItMattersPanel
- WhatToWatchPanel

## Scheduled Release
- CountdownCard
- ActualVsExpectedTable
- ReactionLane
- PriorReleaseCompareCard

## Policy
- QuoteDiffCard
- SpeakerStanceMap
- GuidanceShiftPill

## Breaking Shock
- UncertaintyLadder
- GeoExposureMap
- ContagionChain

## Slow-burn
- ThemeRiver
- TurningPointRail
- SnapshotCompareCard

## Watchlist / Exposure
- DriverExposureMatrix
- ImpactRankList
- ExposureChainCard

---

# 25. 가장 중요한 한 줄 정리

> **차별화는 “더 많은 기사”가 아니라 “track mode에 따라 다른 질문, 다른 상태기계, 다른 추적 surface를 주는 UX”에서 나온다.**

즉, 이 제품의 main UI는 dashboard가 아니라,
실제로는 **stateful tracking experience**여야 한다.

---

# 26. 구현 우선순위

## Phase 1 — MVP
- Home / Inbox
- Track creation wizard
- Scheduled Release mode
- Policy mode
- Story detail
- Evidence drawer
- State-change alerts

## Phase 2
- Breaking Shock mode
- Slow-burn Theme mode
- Watchlist / Exposure mode
- Memory snapshots
- Collaboration notes

## Phase 3
- Compare tracks
- graph read model
- decision journal
- analyst handoff workflows

---

# 27. References

1. AlphaSense, *Smart Summaries*. https://www.alpha-sense.com/platform/smart-summaries/
2. AlphaSense Help Center, *Maximizing Your Monitoring Tools in AlphaSense*. https://help.alpha-sense.com/hc/en-us/articles/41815509396371-Maximizing-Your-Monitoring-Tools-in-AlphaSense
3. LSEG, *LSEG Events* dataset page. https://www.lseg.com/en/data-analytics/financial-data/company-data/company-events-coverage-data
4. LSEG, *Events Calendar* fact sheet. https://www.lseg.com/content/dam/data-analytics/en_us/documents/fact-sheets/events-calendar-factsheet.pdf
5. Refinitiv / LSEG, *Watchlist Pulse App* quick reference card. https://video.training.refinitiv.com/elearning_video/Documents/Eikon_QRC/Eikon%20Quick%20Reference%20Card%20-%20Watchlist%20Pulse%20App.pdf
6. Dataminr, *Geovisualization with Dataminr Pulse*. https://www.dataminr.com/pulse/corporate-security/geovisualization/
7. Event Registry Help Center, *Display options for events*. https://help.eventregistry.org/tag/display-options-for-events/
8. Leban et al., *Event Registry – Learning About World Events From News*. https://archives.iw3c2.org/www2014/proceedings/companion/p107.pdf
9. Nguyen et al., *SchemaLine: Timeline Visualization for Sensemaking*. https://vis4sense.github.io/schemaline/paper.pdf
10. AHRQ PSNet, *Alert Fatigue*. https://psnet.ahrq.gov/primer/alert-fatigue
11. Nielsen Norman Group, *Progressive Disclosure*. https://www.nngroup.com/articles/progressive-disclosure/
12. Reuters Institute, *Digital News Report 2024*. https://reutersinstitute.politics.ox.ac.uk/sites/default/files/2024-06/RISJ_DNR_2024_Digital_v10%20lr.pdf
