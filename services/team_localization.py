from __future__ import annotations

from config.preferences import read_preferences

TEAM_LOCALES: dict[int, dict[str, str]] = {
    108: {"en":"Los Angeles Angels","ko":"LA 에인절스","ko_short":"에인절스","ja":"ロサンゼルス・エンゼルス","ja_short":"エンゼルス"},
    109: {"en":"Arizona Diamondbacks","ko":"애리조나 다이아몬드백스","ko_short":"다이아몬드백스","ja":"アリゾナ・ダイヤモンドバックス","ja_short":"ダイヤモンドバックス"},
    110: {"en":"Baltimore Orioles","ko":"볼티모어 오리올스","ko_short":"오리올스","ja":"ボルチモア・オリオールズ","ja_short":"オリオールズ"},
    111: {"en":"Boston Red Sox","ko":"보스턴 레드삭스","ko_short":"레드삭스","ja":"ボストン・レッドソックス","ja_short":"レッドソックス"},
    112: {"en":"Chicago Cubs","ko":"시카고 컵스","ko_short":"컵스","ja":"シカゴ・カブス","ja_short":"カブス"},
    113: {"en":"Cincinnati Reds","ko":"신시내티 레즈","ko_short":"레즈","ja":"シンシナティ・レッズ","ja_short":"レッズ"},
    114: {"en":"Cleveland Guardians","ko":"클리블랜드 가디언스","ko_short":"가디언스","ja":"クリーブランド・ガーディアンズ","ja_short":"ガーディアンズ"},
    115: {"en":"Colorado Rockies","ko":"콜로라도 로키스","ko_short":"로키스","ja":"コロラド・ロッキーズ","ja_short":"ロッキーズ"},
    116: {"en":"Detroit Tigers","ko":"디트로이트 타이거스","ko_short":"타이거스","ja":"デトロイト・タイガース","ja_short":"タイガース"},
    117: {"en":"Houston Astros","ko":"휴스턴 애스트로스","ko_short":"애스트로스","ja":"ヒューストン・アストロズ","ja_short":"アストロズ"},
    118: {"en":"Kansas City Royals","ko":"캔자스시티 로열스","ko_short":"로열스","ja":"カンザスシティ・ロイヤルズ","ja_short":"ロイヤルズ"},
    119: {"en":"Los Angeles Dodgers","ko":"LA 다저스","ko_short":"다저스","ja":"ロサンゼルス・ドジャース","ja_short":"ドジャース"},
    120: {"en":"Washington Nationals","ko":"워싱턴 내셔널스","ko_short":"내셔널스","ja":"ワシントン・ナショナルズ","ja_short":"ナショナルズ"},
    121: {"en":"New York Mets","ko":"뉴욕 메츠","ko_short":"메츠","ja":"ニューヨーク・メッツ","ja_short":"メッツ"},
    133: {"en":"Athletics","ko":"애슬레틱스","ko_short":"애슬레틱스","ja":"アスレチックス","ja_short":"アスレチックス"},
    134: {"en":"Pittsburgh Pirates","ko":"피츠버그 파이리츠","ko_short":"파이리츠","ja":"ピッツバーグ・パイレーツ","ja_short":"パイレーツ"},
    135: {"en":"San Diego Padres","ko":"샌디에이고 파드리스","ko_short":"파드리스","ja":"サンディエゴ・パドレス","ja_short":"パドレス"},
    136: {"en":"Seattle Mariners","ko":"시애틀 매리너스","ko_short":"매리너스","ja":"シアトル・マリナーズ","ja_short":"マリナーズ"},
    137: {"en":"San Francisco Giants","ko":"샌프란시스코 자이언츠","ko_short":"자이언츠","ja":"サンフランシスコ・ジャイアンツ","ja_short":"ジャイアンツ"},
    138: {"en":"St. Louis Cardinals","ko":"세인트루이스 카디널스","ko_short":"카디널스","ja":"セントルイス・カージナルス","ja_short":"カージナルス"},
    139: {"en":"Tampa Bay Rays","ko":"탬파베이 레이스","ko_short":"레이스","ja":"タンパベイ・レイズ","ja_short":"レイズ"},
    140: {"en":"Texas Rangers","ko":"텍사스 레인저스","ko_short":"레인저스","ja":"テキサス・レンジャーズ","ja_short":"レンジャーズ"},
    141: {"en":"Toronto Blue Jays","ko":"토론토 블루제이스","ko_short":"블루제이스","ja":"トロント・ブルージェイズ","ja_short":"ブルージェイズ"},
    142: {"en":"Minnesota Twins","ko":"미네소타 트윈스","ko_short":"트윈스","ja":"ミネソタ・ツインズ","ja_short":"ツインズ"},
    143: {"en":"Philadelphia Phillies","ko":"필라델피아 필리스","ko_short":"필리스","ja":"フィラデルフィア・フィリーズ","ja_short":"フィリーズ"},
    144: {"en":"Atlanta Braves","ko":"애틀랜타 브레이브스","ko_short":"브레이브스","ja":"アトランタ・ブレーブス","ja_short":"ブレーブス"},
    145: {"en":"Chicago White Sox","ko":"시카고 화이트삭스","ko_short":"화이트삭스","ja":"シカゴ・ホワイトソックス","ja_short":"ホワイトソックス"},
    146: {"en":"Miami Marlins","ko":"마이애미 말린스","ko_short":"말린스","ja":"マイアミ・マーリンズ","ja_short":"マーリンズ"},
    147: {"en":"New York Yankees","ko":"뉴욕 양키스","ko_short":"양키스","ja":"ニューヨーク・ヤンキース","ja_short":"ヤンキース"},
    158: {"en":"Milwaukee Brewers","ko":"밀워키 브루어스","ko_short":"브루어스","ja":"ミルウォーキー・ブルワーズ","ja_short":"ブルワーズ"},
}
ALIASES={"Oakland Athletics":133,"Las Vegas Athletics":133,"A's":133}

def _language() -> str:
    lang=str(read_preferences().get("language","en"))
    return lang if lang in {"en","ko","ja"} else "en"

def localized_team_name(team_id:int|None, english_name:str, language:str|None=None, *, short:bool=False)->str:
    language=language or _language()
    if language=="en":
        return english_name
    resolved=int(team_id or 0)
    if not resolved:
        folded=english_name.casefold()
        for tid,row in TEAM_LOCALES.items():
            if row["en"].casefold()==folded:
                resolved=tid; break
        if not resolved:
            resolved=ALIASES.get(english_name,0)
    row=TEAM_LOCALES.get(resolved)
    if not row:
        return english_name
    return row.get(f"{language}_short" if short else language) or row.get(language) or english_name

def apply_team_ref(team, language:str|None=None)->None:
    language=language or _language()
    if language=="en":
        return
    original=str(getattr(team,"name","") or "")
    team.name=localized_team_name(getattr(team,"id",0),original,language)
    team.abbreviation=localized_team_name(getattr(team,"id",0),original,language,short=True)
