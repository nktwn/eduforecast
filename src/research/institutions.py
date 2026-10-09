from dataclasses import dataclass

UNIVERSITY_TYPE_PLACEHOLDER = "TODO"

FOUNDED_FALLBACK = {"NU": 2010}


@dataclass(frozen=True)
class University:
    key: str
    openalex_id: str
    name: str
    ror: str
    country: str
    group: str


UNIVERSITIES: list[University] = [
    University("NU", "I60559429", "Nazarbayev University", "052bx8q98", "KZ", "kz"),
    University("KBTU", "I171571821", "Kazakh-British Technical University", "01rn0fp76", "KZ", "kz"),
    University("SDU", "I4210120897", "Suleyman Demirel University", "02s8x5a25", "KZ", "kz"),
    University("SATBAYEV", "I204275683", "Satbayev University", "020cpsb96", "KZ", "kz"),
    University("KAZNU", "I185571130", "Al-Farabi Kazakh National University", "03q0vrn42", "KZ", "kz"),
    University("ENU", "I10232997", "L. N. Gumilyov Eurasian National University", "0242cby63", "KZ", "kz"),
    University("NARXOZ", "I3130577743", "Narxoz University", "0523w7v09", "KZ", "kz"),
    University("KIMEP", "I869467088", "KIMEP University", "01pk2ck74", "KZ", "kz"),
    University("SHAKARIM", "I4210159258", "Shakarim University", "052q3p191", "KZ", "kz"),
    University("AITU", "I4405257690", "Astana IT University", "05jnvbc31", "KZ", "kz"),
    University("SKOLTECH", "I125989756", "Skolkovo Institute of Science and Technology", "03f9nc143", "RU", "benchmark"),
    University("INNOPOLIS", "I4210116741", "Innopolis University", "02b7jh107", "RU", "benchmark"),
    University("UNIST", "I48566637", "Ulsan National Institute of Science and Technology", "017cjz748", "KR", "benchmark"),
    University("MBZUAI", "I4210113480", "Mohamed bin Zayed University of Artificial Intelligence", "0258gkt32", "AE", "benchmark"),
]

BY_KEY = {u.key: u for u in UNIVERSITIES}
