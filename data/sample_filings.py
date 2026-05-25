"""
sample_filings.py
-----------------
Representative excerpts from Apple, Microsoft, and Google 10-K filings.
These are used to seed the FAISS vector store for RAG demonstrations.
All figures are based on publicly reported financials.
"""

SAMPLE_FILINGS: list[dict] = [
    # ─── APPLE INC. ────────────────────────────────────────────────────────────
    {
        "company": "Apple Inc.",
        "ticker": "AAPL",
        "filing": "10-K FY2023",
        "section": "Business Overview",
        "text": (
            "Apple Inc. designs, manufactures, and markets smartphones, personal computers, tablets, "
            "wearables, and accessories worldwide. The Company's fiscal year 2023 net sales were $383.3 billion, "
            "a decline of 2.8% compared to $394.3 billion in fiscal year 2022. iPhone revenue was $200.6 billion, "
            "representing approximately 52% of total net sales. Services revenue reached an all-time high of "
            "$85.2 billion, growing 9% year-over-year, reflecting strength in the App Store, Apple Music, "
            "Apple TV+, iCloud, and Apple Pay. The Company operates retail stores in 26 countries and employs "
            "approximately 161,000 full-time equivalent employees."
        ),
    },
    {
        "company": "Apple Inc.",
        "ticker": "AAPL",
        "filing": "10-K FY2023",
        "section": "Risk Factors",
        "text": (
            "Apple's business is subject to numerous risks. Global and regional economic conditions may "
            "materially adversely affect the Company's net sales, gross margins, and operating results. "
            "The Company's business faces intense competition from well-resourced competitors. Apple relies "
            "on sole-source or limited-source suppliers for certain components including OLED displays and "
            "advanced chips manufactured by TSMC. Geopolitical tensions, particularly between the United States "
            "and China, represent a material risk given that a significant portion of the Company's products "
            "are assembled in China. Changes in trade policies, tariffs, and export restrictions could "
            "negatively impact product availability and margins."
        ),
    },
    {
        "company": "Apple Inc.",
        "ticker": "AAPL",
        "filing": "10-K FY2023",
        "section": "Financial Highlights",
        "text": (
            "For fiscal year 2023, Apple reported gross margin of $169.1 billion (44.1%), operating income "
            "of $114.3 billion, and net income of $97.0 billion ($6.16 diluted EPS). The Company generated "
            "$110.5 billion in operating cash flow and returned over $89 billion to shareholders through "
            "dividends and share repurchases. Cash and cash equivalents plus marketable securities totaled "
            "$162.1 billion. Capital expenditures were $10.7 billion, primarily for data centers and "
            "retail build-outs. Research and development expense was $29.9 billion, representing 7.8% of "
            "net sales, reflecting investment in silicon design, AI, and next-generation product development."
        ),
    },
    {
        "company": "Apple Inc.",
        "ticker": "AAPL",
        "filing": "10-K FY2023",
        "section": "Segment Results",
        "text": (
            "Apple reports results across five segments: iPhone, Mac, iPad, Wearables/Home/Accessories, and "
            "Services. iPhone net sales declined 2% to $200.6 billion due to foreign exchange headwinds and "
            "softening consumer demand in key markets. Mac net sales fell 27% to $29.4 billion reflecting "
            "post-pandemic demand normalization. iPad net sales decreased 3% to $28.3 billion. "
            "Wearables, Home, and Accessories segment generated $39.8 billion, down 3%. Services was the "
            "standout performer, reaching $85.2 billion, with gross margin of 70.8%, significantly above "
            "the company-wide average, making it the highest-margin segment and a key driver of future "
            "profitability improvement."
        ),
    },
    {
        "company": "Apple Inc.",
        "ticker": "AAPL",
        "filing": "10-K FY2023",
        "section": "Capital Return Program",
        "text": (
            "Apple's board of directors declared a cash dividend of $0.24 per share of the Company's common "
            "stock for fiscal Q4 2023. Since initiating its capital return program in 2012, Apple has returned "
            "over $650 billion to shareholders. In fiscal 2023, the Company repurchased $77.6 billion of its "
            "common stock under its share repurchase program. Apple's board authorized an additional $90 billion "
            "for share repurchases in May 2023. The Company targets a net cash neutral position over time and "
            "continues to opportunistically lever up the balance sheet to fund repurchases while maintaining "
            "its AA+ credit rating."
        ),
    },

    # ─── MICROSOFT CORPORATION ─────────────────────────────────────────────────
    {
        "company": "Microsoft Corporation",
        "ticker": "MSFT",
        "filing": "10-K FY2023",
        "section": "Business Overview",
        "text": (
            "Microsoft Corporation is a technology company headquartered in Redmond, Washington. "
            "Fiscal year 2023 revenue was $211.9 billion, a 7% increase year-over-year. The Company "
            "operates through three segments: Productivity and Business Processes ($69.3 billion), "
            "Intelligent Cloud ($87.9 billion), and More Personal Computing ($54.7 billion). "
            "Microsoft Azure, the Company's cloud computing platform, continues to take market share "
            "and grew 27% in constant currency. The $69 billion acquisition of Activision Blizzard, "
            "pending regulatory review, represents the Company's largest acquisition and is intended "
            "to accelerate growth in the gaming segment. Microsoft employs approximately 221,000 "
            "full-time employees globally."
        ),
    },
    {
        "company": "Microsoft Corporation",
        "ticker": "MSFT",
        "filing": "10-K FY2023",
        "section": "Cloud & AI Strategy",
        "text": (
            "Microsoft has made significant investments in artificial intelligence, including a multi-year, "
            "multi-billion dollar partnership with OpenAI. The Company has integrated AI capabilities "
            "across its product portfolio, launching Microsoft 365 Copilot, GitHub Copilot, Azure OpenAI "
            "Service, and Bing Chat powered by GPT-4. Azure AI services revenue has grown substantially, "
            "contributing to Intelligent Cloud segment outperformance. The Company committed to investing "
            "$10 billion in OpenAI in January 2023. Management believes AI-powered productivity tools "
            "represent a generational market opportunity, with potential to add trillions of dollars in "
            "economic value globally. Azure's AI infrastructure investments include specialized GPU "
            "clusters and custom silicon."
        ),
    },
    {
        "company": "Microsoft Corporation",
        "ticker": "MSFT",
        "filing": "10-K FY2023",
        "section": "Financial Performance",
        "text": (
            "Microsoft achieved record operating income of $88.5 billion (41.8% margin) and net income "
            "of $72.4 billion ($9.72 diluted EPS) in fiscal year 2023, representing 20% and 3% "
            "year-over-year growth respectively. Operating cash flow was $87.9 billion and free cash "
            "flow was $63.3 billion. The Company returned $9.7 billion in dividends and $22.2 billion "
            "through share repurchases in fiscal 2023. Research and development expense totaled $27.2 "
            "billion. Capital expenditures were $28.1 billion, driven by global data center expansion "
            "to support Azure capacity. The Company holds cash and cash equivalents of $111.3 billion."
        ),
    },
    {
        "company": "Microsoft Corporation",
        "ticker": "MSFT",
        "filing": "10-K FY2023",
        "section": "Risk Factors",
        "text": (
            "Microsoft faces significant competition across all business segments from companies such as "
            "Amazon Web Services, Google Cloud, Salesforce, and Oracle in cloud computing; and from "
            "Apple, Google, and Meta in consumer products. Cybersecurity incidents represent a material "
            "risk; the Company's products and services have been targets of sophisticated nation-state "
            "and criminal actors. Regulatory risk is elevated given ongoing antitrust scrutiny in the "
            "EU and US DOJ review of the Activision Blizzard acquisition. Macroeconomic uncertainty "
            "could reduce enterprise IT spending, negatively impacting cloud and software revenue. "
            "Foreign exchange fluctuations materially impacted reported revenue by approximately "
            "5 percentage points in fiscal 2023."
        ),
    },
    {
        "company": "Microsoft Corporation",
        "ticker": "MSFT",
        "filing": "10-K FY2023",
        "section": "Intelligent Cloud Segment",
        "text": (
            "The Intelligent Cloud segment, which includes Azure, SQL Server, Windows Server, and GitHub, "
            "generated $87.9 billion in revenue in fiscal 2023, representing 27% year-over-year growth. "
            "Azure and other cloud services grew 27% in constant currency and now represent more than "
            "50% of segment revenue. GitHub reached 100 million registered developers in January 2023 "
            "and GitHub Copilot, the AI-powered coding assistant, became the fastest-growing developer "
            "tool in the company's history. Enterprise Mobility and Security surpassed $20 billion in "
            "annual revenue, reflecting strong demand for identity, security, and compliance solutions. "
            "The segment's operating income was $37.9 billion, a 17% margin expansion year-over-year."
        ),
    },

    # ─── ALPHABET INC. (GOOGLE) ────────────────────────────────────────────────
    {
        "company": "Alphabet Inc.",
        "ticker": "GOOGL",
        "filing": "10-K FY2023",
        "section": "Business Overview",
        "text": (
            "Alphabet Inc. is a holding company with Google LLC as its primary wholly-owned subsidiary. "
            "Fiscal year 2023 consolidated revenues were $307.4 billion, a 9% increase year-over-year. "
            "Google Services segment, which includes Google Search, YouTube, and Google Network, generated "
            "$272.5 billion in revenue. Google Cloud generated $33.1 billion, growing 28% year-over-year "
            "and achieving its first full-year operating profit of $1.7 billion. Other Bets, which "
            "includes Waymo and Verily, generated $1.5 billion in revenue with an operating loss of "
            "$1.2 billion. Alphabet employs approximately 182,000 full-time employees as of December 2023."
        ),
    },
    {
        "company": "Alphabet Inc.",
        "ticker": "GOOGL",
        "filing": "10-K FY2023",
        "section": "Advertising Revenue",
        "text": (
            "Google advertising revenues totaled $237.9 billion in fiscal year 2023. Google Search "
            "and Other revenues were $175.0 billion, growing 10% year-over-year, driven by strong "
            "advertiser demand across retail, travel, and financial services verticals. YouTube "
            "advertising revenues were $31.5 billion, representing a recovery from the advertising "
            "market downturn in 2022. Google Network Members' properties revenues were $31.3 billion, "
            "reflecting modest decline due to structural headwinds in display advertising. The Company "
            "launched Search Generative Experience (SGE) powered by Gemini, which management believes "
            "will enhance user engagement and long-term search monetization, though near-term impacts "
            "on click-through rates remain uncertain."
        ),
    },
    {
        "company": "Alphabet Inc.",
        "ticker": "GOOGL",
        "filing": "10-K FY2023",
        "section": "Financial Performance",
        "text": (
            "Alphabet reported operating income of $84.3 billion (27.4% margin) and net income of "
            "$73.8 billion ($5.80 diluted EPS) in fiscal year 2023. The Company generated $101.7 "
            "billion in operating cash flow and $69.5 billion in free cash flow. Capital expenditures "
            "increased to $32.3 billion as the Company invested heavily in AI infrastructure, "
            "including custom TPUs (Tensor Processing Units), data centers, and network infrastructure. "
            "Alphabet repurchased $62.2 billion of Class A and Class C shares in fiscal 2023 and "
            "announced its first-ever quarterly cash dividend of $0.20 per share in April 2024. "
            "Cash, cash equivalents, and short-term marketable securities totaled $110.9 billion."
        ),
    },
    {
        "company": "Alphabet Inc.",
        "ticker": "GOOGL",
        "filing": "10-K FY2023",
        "section": "AI and Innovation",
        "text": (
            "Alphabet has made AI central to its long-term strategy. The Company launched Gemini, its "
            "most capable large language model family, with variants spanning Gemini Ultra, Pro, and Nano "
            "for deployment across Google products and Google Cloud. Bard was relaunched as Gemini "
            "assistant. Google DeepMind was formed by merging Google Brain and DeepMind to concentrate "
            "AI research capabilities. The Company's custom AI accelerator chips, the Tensor Processing "
            "Units (TPUs), provide competitive cost and performance advantages for training and "
            "inference workloads. Google Cloud's Vertex AI platform saw accelerating customer adoption "
            "as enterprises look to build AI-powered applications. Alphabet's total R&D expense was "
            "$45.4 billion in fiscal 2023, representing 14.8% of revenue."
        ),
    },
    {
        "company": "Alphabet Inc.",
        "ticker": "GOOGL",
        "filing": "10-K FY2023",
        "section": "Risk Factors",
        "text": (
            "Alphabet faces material risks from the rapid evolution of AI, which could disrupt its "
            "core search advertising business if competitors offer superior AI-powered alternatives. "
            "The Company is subject to extensive regulatory scrutiny globally; the U.S. DOJ filed "
            "antitrust lawsuits related to Google's dominance in search and advertising technology. "
            "The EU's Digital Markets Act (DMA) designation as a 'gatekeeper' could require significant "
            "changes to Google's business practices. YouTube faces regulatory risk related to content "
            "moderation, copyright enforcement, and children's privacy under COPPA. Foreign exchange "
            "headwinds reduced reported revenue growth by approximately 3 percentage points in fiscal "
            "2023. Competition for AI talent and specialized GPU compute represents an operational risk."
        ),
    },
]
