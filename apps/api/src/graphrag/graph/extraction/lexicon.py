"""Word lists for the rule based extractor.

They are deliberately plain data: a deployment that needs more coverage swaps in a language
model (graph/extraction/llm.py) rather than growing these lists.
"""

from __future__ import annotations


def _words(text: str) -> frozenset[str]:
    return frozenset(text.split())


FIRST_NAMES = _words(
    """aaron abigail adam adrian aisha alan albert alejandro alex alexander alice alicia amara
    amelia amir amy ana andrea andrew angela anita anna anthony antonio arjun arthur asha ashley
    ava barbara ben benjamin beth bianca bill bob brian bruno camila carl carlos carmen caroline
    catherine chen chloe chris christian christine claire claudia colin craig dana daniel
    david deborah diana diego dmitri dominic donald dorothy edward elena eli elizabeth ella emily
    emma eric erik ethan eva evelyn fatima felix fiona frances francisco frank gabriel gabriela
    george grace greg hana hannah harold harry hassan hector helen henry hiro hugo ian ibrahim
    igor imani irene isaac isabel ivan jack jacob james jamal jane janet jason javier jean jeff
    jennifer jeremy jessica jian jin joan joao joel john jonas jonathan jorge jose joseph joshua
    juan judith julia julian julie justin karen karim kate katherine kavya kenji kevin kim kofi
    kwame lars laura lauren leah lena leo leon leonardo li lily linda lisa liu lorenzo louis lucas
    lucia luis luke lukas maria marcus margaret maria mariam mario mark marta martin mary
    mateo matthew maya megan mei michael michelle miguel mika mira miriam mohamed mohammed monica
    nadia naomi nathan neil nicholas nick nicole nina noah nora oliver olivia omar oscar pablo
    pam patricia patrick paul pedro peter philip priya rachel rafael rahul raj ravi rebecca
    richard rita robert roberto rosa ruth ryan sakura samir samuel sandra sara sarah scott sean
    sergio shirin simon sofia sophia stefan stephen steven sunita susan tamar tara teresa thomas
    tim timothy tomas tony uma valentina vera victor victoria vijay vincent wei wendy william
    xavier yara yasmin yuki yusuf zainab zara zoe"""
)

# Capitalized words that start sentences or fill phrases but are not names.
STARTERS = _words(
    """The A An In On At By For With From To Of And But Or So Yet As If When While Where After
    Before During Since Until Although Because However Meanwhile Moreover Furthermore Therefore
    Thus Then Also Still Later Earlier Today Yesterday Tomorrow This That These Those It Its
    They Their There Here He She His Her We Our You Your I My One Some Many Most Each Every
    All Both Such What Which Who Whom Whose How Why Not No Yes Over Under Between Among Within
    Without Across Through Into Onto Upon About Against Despite Instead Overall Today Recently
    Currently Previously Initially Finally First Second Third Last Next New Another Other Several
    Both Either Neither According Following Based Given Under Per Via Whether Once Although
    Now Early Late Soon Together Unlike Like Beyond Throughout Around Near"""
)

NOISE = _words(
    """Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May
    June July August September October November December Q1 Q2 Q3 Q4 English French German
    Spanish Chinese Japanese American European African Asian Indian Mr Ms Mrs Dr Prof Sir
    Fig Figure Table Section Chapter Page Yes"""
)

PERSON_TITLES = frozenset({"dr", "prof", "professor", "mr", "ms", "mrs", "sir"})
ROLE_WORDS = _words(
    """ceo cto cfo coo cio founder co-founder cofounder director professor engineer scientist
    researcher chair chairman chairwoman president minister analyst lead head manager investor
    partner author editor architect physician surgeon vp"""
)
ROLE_LEADS = _words(
    "ceo cto cfo coo cio chair chairman chairwoman president director head lead minister"
)
ROLE_FOUNDS = _words("founder co-founder cofounder")

ORG_SUFFIXES = _words(
    """inc corp corporation ltd llc plc gmbh co company labs lab systems technologies technology
    institute university college foundation group partners capital ventures agency council
    ministry bank robotics dynamics industries motors energy networks works collective alliance
    association society consortium authority department commission hospital laboratories
    solutions logistics analytics holdings studios airlines airways railways petroleum
    pharmaceuticals therapeutics biosciences semiconductors electronics manufacturing
    mining shipping fund exchange"""
)
EVENT_SUFFIXES = _words(
    """summit conference expo symposium hackathon forum festival prize award treaty accord
    crisis war challenge championship workshop congress convention"""
)
PRODUCT_SUFFIXES = _words(
    """platform engine os cloud suite toolkit studio drive pro cell chip sensor battery robot
    rover drone pack kit api sdk app cobot lidar scanner module gateway hauler charger twin truck carrier"""
)
TECH_SUFFIXES = _words(
    """protocol algorithm framework architecture standard language library method learning
    intelligence computing"""
)
LOCATION_SUFFIXES = _words(
    "city river bay valley island islands province strait port mountains canyon coast"
)

# Whole names (folded) that are places.
LOCATIONS = frozenset(
    c.strip()
    for c in """afghanistan argentina australia austria bangladesh belgium brazil canada chile china
    colombia croatia cuba denmark egypt estonia ethiopia finland france germany ghana greece
    hungary iceland india indonesia iran iraq ireland israel italy japan jordan kenya korea
    kuwait latvia lebanon malaysia mexico morocco nepal netherlands nigeria norway pakistan peru
    philippines poland portugal qatar romania russia rwanda singapore slovakia slovenia spain
    sweden switzerland taiwan tanzania thailand turkey uganda ukraine uruguay venezuela vietnam
    zambia zimbabwe europe asia africa antarctica oceania scandinavia the-netherlands
    united-states united-kingdom united-arab-emirates south-korea north-america south-america
    saudi-arabia south-africa new-zealand hong-kong
    amsterdam athens atlanta austin bangalore bangkok barcelona beijing berlin boston brisbane
    brussels budapest cairo calgary chicago copenhagen dallas delhi denver detroit dubai dublin
    edinburgh frankfurt geneva hamburg helsinki houston istanbul jakarta johannesburg karachi
    kyoto lagos lima lisbon london lyon madrid manchester manila melbourne miami milan montreal
    moscow mumbai munich nairobi osaka oslo ottawa paris perth pittsburgh prague pune rome
    rotterdam seattle seoul shanghai shenzhen stockholm sydney taipei tallinn tokyo toronto
    vancouver vienna warsaw zurich singapore california texas florida ontario bavaria
    silicon-valley bay-area""".replace("\n", " ").split()
)

ORG_VERBS = _words(
    """announced acquired launched raised partnered signed opened expanded supplies supplied
    manufactures manufactured operates operated employs employed reported released invested
    merged unveiled acquires announces launches partners builds built develops developed
    deployed deploys hired plans planned runs ran sells sold ships shipped delivers delivered
    competes competed funded funds opened closed"""
)
PERSON_VERBS = _words(
    """said says joined joins leads led founded argued argues noted notes explained explains
    told resigned studied wrote writes presented presents believes believed stated added
    recalled warned predicted appointed hired mentored"""
)

# Acronyms (folded) and the type they usually denote.
TECH_ACRONYMS = _words(
    """ai ml llm llms gpu gpus cpu cpus api apis sdk rag iot lidar slam ros nlp ocr gps rfid
    5g 4g wifi ssd dram hbm tpu fpga asic sql etl erp crm cad plc scada mqtt grpc http"""
)
ORG_ACRONYMS = _words(
    """nasa who eu un nato imf nist iso ieee acm mit nsf fda epa wto oecd ibm sap"""
)

# Lowercase terms worth keeping as concepts (folded) mapped to a type.
CONCEPT_TERMS: dict[str, str] = {
    "knowledge graph": "CONCEPT",
    "knowledge graphs": "CONCEPT",
    "machine learning": "TECHNOLOGY",
    "deep learning": "TECHNOLOGY",
    "reinforcement learning": "TECHNOLOGY",
    "federated learning": "TECHNOLOGY",
    "neural network": "TECHNOLOGY",
    "neural networks": "TECHNOLOGY",
    "computer vision": "TECHNOLOGY",
    "large language model": "TECHNOLOGY",
    "large language models": "TECHNOLOGY",
    "vector database": "TECHNOLOGY",
    "sensor fusion": "TECHNOLOGY",
    "digital twin": "TECHNOLOGY",
    "digital twins": "TECHNOLOGY",
    "edge computing": "TECHNOLOGY",
    "solid-state battery": "TECHNOLOGY",
    "lithium-sulfur battery": "TECHNOLOGY",
    "autonomous navigation": "TECHNOLOGY",
    "predictive maintenance": "CONCEPT",
    "warehouse automation": "CONCEPT",
    "supply chain": "CONCEPT",
    "supply chains": "CONCEPT",
    "retrieval-augmented generation": "TECHNOLOGY",
    "carbon capture": "TECHNOLOGY",
    "renewable energy": "CONCEPT",
    "battery recycling": "CONCEPT",
    "data governance": "CONCEPT",
    "model governance": "CONCEPT",
    "entity resolution": "CONCEPT",
    "community detection": "CONCEPT",
    "graph database": "TECHNOLOGY",
    "graph neural network": "TECHNOLOGY",
    "vector search": "TECHNOLOGY",
    "last-mile delivery": "CONCEPT",
    "cold chain": "CONCEPT",
    "quantum computing": "TECHNOLOGY",
    "semantic search": "TECHNOLOGY",
}
