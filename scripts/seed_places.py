"""รายชื่อสถานที่เด่นรายจังหวัด (ชื่อบทความ en.wikipedia) เป็น "รายการตั้งต้น" ให้ build_places.py ไปดึงพิกัดและชื่อไทยจาก Wikipedia

ข้อเท็จจริงทั้งหมด (พิกัด ชื่อไทย) มาจาก Wikipedia ตอนดึง ไม่ได้มาจากไฟล์นี้
ไฟล์นี้เป็นเพียง "ใครเด่นในจังหวัดไหน" (การเลือกของทีม) กับป้ายหมวด (ป้ายของทีม ไม่ใช่ข้อเท็จจริงที่ตรวจแล้ว)

รหัสหมวด: T=วัด/ศาสนสถาน N=ธรรมชาติ(อุทยาน น้ำตก ถ้ำ) B=ทะเล/เกาะ H=โบราณสถาน/อุทยานประวัติศาสตร์ M=พิพิธภัณฑ์/วัง K=ตลาด A=กิจกรรม/จุดชมวิว/แลนด์มาร์ก
"""
CODES = {
    "T": ("temple", ["culture", "photo"], 60),
    "N": ("nature", ["nature", "outdoors", "photo"], 120),
    "B": ("nature", ["nature", "outdoors", "relax", "photo"], 150),
    "H": ("museum", ["history", "culture", "outdoors"], 120),
    "M": ("museum", ["culture", "rainy_ok", "history"], 90),
    "K": ("market", ["market", "food", "local"], 90),
    "A": ("activity", ["family", "photo"], 90),
}

# จังหวัด -> [(ชื่อบทความ en.wikipedia, รหัสหมวด)]
SEED = {
    'กรุงเทพมหานคร': [('Grand_Palace', 'M'), ('Wat_Pho', 'T'), ('Wat_Arun', 'T'), ('Wat_Saket', 'T'), ('Jim_Thompson_House', 'M'), ('Chatuchak_Weekend_Market', 'K'), ('Lumphini_Park', 'N'), ('Wat_Benchamabophit', 'T'), ('Erawan_Shrine', 'T'), ('Bangkok_National_Museum', 'M'), ('Giant_Swing', 'A'), ('Democracy_Monument,_Bangkok', 'A'), ('Wat_Traimit', 'T'), ('Vimanmek_Mansion', 'M'), ('Suan_Pakkad_Palace', 'M'), ('Asiatique_The_Riverfront', 'K'), ('Khao_San_Road', 'K'), ('Bang_Krachao', 'N'), ('Wat_Ratchanatdaram', 'T'), ('Golden_Mount,_Bangkok', 'A')],
    'กระบี่': [('Ao_Nang', 'B'), ('Railay_Beach', 'B'), ('Phi_Phi_Islands', 'B'), ('Tiger_Cave_Temple_(Krabi)', 'T'), ('Hong_Islands', 'B'), ('Khao_Phanom_Bencha_National_Park', 'N'), ('Ko_Lanta', 'B'), ('Thung_Teao_Forest_Natural_Park', 'N'), ('Ko_Poda', 'B')],
    'กาญจนบุรี': [('Bridge_on_the_River_Kwai', 'A'), ('Erawan_National_Park', 'N'), ('Hellfire_Pass', 'H'), ('Sai_Yok_National_Park', 'N'), ('Kanchanaburi_War_Cemetery', 'H'), ('JEATH_War_Museum', 'M'), ('Thung_Yai_Naresuan_Wildlife_Sanctuary', 'N'), ('Khao_Laem_National_Park', 'N'), ('Srinagarind_Dam', 'A')],
    'กาฬสินธุ์': [('Sirindhorn_Museum', 'M'), ('Lam_Pao_Dam', 'A'), ('Phu_Kum_Khao_Dinosaur_Site', 'H')],
    'กำแพงเพชร': [('Kamphaeng_Phet_Historical_Park', 'H'), ('Khlong_Lan_National_Park', 'N'), ('Khlong_Wang_Chao_National_Park', 'N'), ('Mae_Wong_National_Park', 'N')],
    'ขอนแก่น': [('Phu_Wiang_National_Park', 'N'), ('Ubolratana_Dam', 'A'), ('Phu_Pha_Man_National_Park', 'N'), ('Bueng_Kaen_Nakhon', 'A'), ('Phu_Wiang_Dinosaur_Museum', 'M')],
    'จันทบุรี': [('Khao_Khitchakut_National_Park', 'N'), ('Namtok_Phlio_National_Park', 'N'), ('Laem_Sing', 'B'), ('Cathedral_of_the_Immaculate_Conception,_Chanthaburi', 'T'), ('Kung_Krabaen_Bay', 'B'), ('Khao_Sip_Ha_Chan', 'N')],
    'ฉะเชิงเทรา': [('Wat_Sothon_Wararam_Worawihan', 'T'), ('Wat_Pho_Bang_Khla', 'T'), ('Khao_Hin_Son', 'N')],
    'ชลบุรี': [('Pattaya', 'B'), ('Sanctuary_of_Truth', 'M'), ('Ko_Si_Chang', 'B'), ('Khao_Kheow_Open_Zoo', 'A'), ('Bang_Saen', 'B'), ('Nong_Nooch_Tropical_Garden', 'A'), ('Wat_Yansangwararam', 'T'), ('Khao_Chi_Chan', 'A'), ('Ko_Larn', 'B'), ('Pattaya_Floating_Market', 'K')],
    'ชัยนาท': [('Chao_Phraya_Dam', 'A'), ('Chai_Nat_Bird_Park', 'A'), ('Wat_Phra_Borommathat_Woramahawihan', 'T')],
    'ชัยภูมิ': [('Pa_Hin_Ngam_National_Park', 'N'), ('Tat_Ton_National_Park', 'N'), ('Sai_Thong_National_Park', 'N'), ('Phu_Khiao_Wildlife_Sanctuary', 'N')],
    'ชุมพร': [('Mu_Ko_Chumphon_National_Park', 'B'), ('Hat_Sai_Ri', 'B'), ('Tham_Khao_Phlai', 'N')],
    'เชียงราย': [('Wat_Rong_Khun', 'T'), ('Baan_Dam_Museum', 'M'), ('Wat_Rong_Suea_Ten', 'T'), ('Doi_Tung', 'N'), ('Golden_Triangle_(Southeast_Asia)', 'A'), ('Phu_Chi_Fa', 'N'), ('Wat_Huay_Pla_Kang', 'T'), ('Chiang_Rai_Clock_Tower', 'A'), ('Doi_Mae_Salong', 'N'), ('Mae_Fah_Luang_Garden', 'N')],
    'ตรัง': [('Hat_Chao_Mai_National_Park', 'B'), ('Ko_Kradan', 'B'), ('Ko_Libong', 'B'), ('Ko_Mook', 'B'), ('Tham_Morakot', 'N')],
    'ตราด': [('Ko_Chang', 'B'), ('Ko_Kood', 'B'), ('Mu_Ko_Chang_National_Park', 'B'), ('Ko_Mak', 'B'), ('Ko_Wai', 'B')],
    'ตาก': [('Mae_Sot', 'A'), ('Bhumibol_Dam', 'A'), ('Thi_Lo_Su_Waterfall', 'N'), ('Taksin_Maharat_National_Park', 'N'), ('Lan_Sang_National_Park', 'N'), ('Um_Phang_Wildlife_Sanctuary', 'N')],
    'นครนายก': [('Nang_Rong_Waterfall', 'N'), ('Sarika_Waterfall', 'N'), ('Khun_Dan_Prakarn_Chon_Dam', 'A')],
    'นครปฐม': [('Phra_Pathommachedi', 'T'), ('Sanam_Chandra_Palace', 'M'), ('Don_Wai_Market', 'K'), ('Rose_Garden_Riverside', 'A'), ('Phra_Pathom_Chedi_National_Museum', 'M')],
    'นครพนม': [('Wat_Phra_That_Phanom', 'T'), ('Phu_Langka_National_Park', 'N')],
    'นครราชสีมา': [('Phimai_Historical_Park', 'H'), ('Khao_Yai_National_Park', 'N'), ('Thao_Suranari_Monument', 'A'), ('Wat_Sala_Loi', 'T'), ('Dan_Kwian', 'K'), ('Wat_Phra_Narai_Maharat', 'T'), ('Phu_Ruea', 'N')],
    'นครศรีธรรมราช': [('Wat_Phra_Mahathat_Woramahawihan', 'T'), ('Khao_Luang_National_Park', 'N'), ('Khanom', 'B'), ('Nakhon_Si_Thammarat_National_Museum', 'M'), ('Khao_Luang_(Nakhon_Si_Thammarat)', 'N')],
    'นครสวรรค์': [('Bueng_Boraphet', 'N'), ('Wat_Khiriwong', 'T')],
    'นนทบุรี': [('Ko_Kret', 'A'), ('Wat_Poramai_Yikawat', 'T'), ('Wat_Chaloem_Phra_Kiat_Worawihan', 'T'), ('Nonthaburi_Pier', 'A')],
    'นราธิวาส': [('Taksin_Ratchaniwet_Palace', 'M'), ('Hala-Bala_Wildlife_Sanctuary', 'N'), ('Bacho_Waterfall', 'N')],
    'น่าน': [('Wat_Phumin', 'T'), ('Wat_Phra_That_Chae_Haeng', 'T'), ('Doi_Phu_Kha_National_Park', 'N'), ('Wat_Phra_That_Khao_Noi', 'T'), ('Bo_Kluea', 'A'), ('Nan_National_Museum', 'M'), ('Sri_Nan_National_Park', 'N'), ('Wat_Phra_That_Chang_Kham', 'T')],
    'บึงกาฬ': [('Phu_Wua_Wildlife_Sanctuary', 'N'), ('Wat_Phu_Tok', 'T')],
    'บุรีรัมย์': [('Phanom_Rung_Historical_Park', 'H'), ('Prasat_Mueang_Tam', 'H'), ('Khao_Kradong_Forest_Park', 'N'), ('Chang_International_Circuit', 'A'), ('Wat_Khao_Angkhan', 'T')],
    'ปทุมธานี': [('Wat_Phra_Dhammakaya', 'T'), ('Dream_World_(Thailand)', 'A'), ('Siam_Amazing_Park', 'A'), ('Wat_Sing', 'T')],
    'ประจวบคีรีขันธ์': [('Hua_Hin', 'B'), ('Khao_Sam_Roi_Yot_National_Park', 'N'), ('Phraya_Nakhon_Cave', 'N'), ('Klai_Kangwon_Palace', 'M'), ('Hua_Hin_railway_station', 'A'), ('Wat_Huay_Mongkol', 'T'), ('Hua_Hin_Night_Market', 'K')],
    'ปราจีนบุรี': [('Thap_Lan_National_Park', 'N'), ('Si_Mahosot', 'H')],
    'ปัตตานี': [('Krue_Se_Mosque', 'T'), ('Pattani_Central_Mosque', 'T'), ('Lim_Ko_Niao_Shrine', 'T')],
    'พระนครศรีอยุธยา': [('Ayutthaya_Historical_Park', 'H'), ('Wat_Mahathat_(Ayutthaya)', 'T'), ('Wat_Phra_Si_Sanphet', 'T'), ('Wat_Chaiwatthanaram', 'T'), ('Bang_Pa-In_Royal_Palace', 'M'), ('Wat_Yai_Chai_Mongkhon', 'T'), ('Wat_Phanan_Choeng', 'T'), ('Wihan_Phra_Mongkhon_Bophit', 'T'), ('Wat_Lokayasutharam', 'T'), ('Chao_Sam_Phraya_National_Museum', 'M'), ('Wat_Ratchaburana_(Ayutthaya)', 'T'), ('Wat_Phutthaisawan', 'T')],
    'พะเยา': [('Kwan_Phayao', 'N'), ('Wat_Si_Khom_Kham', 'T'), ('Phu_Sang_National_Park', 'N'), ('Wat_Analayo_Thipphayaram', 'T'), ('Doi_Phu_Nang_National_Park', 'N')],
    'พังงา': [('Phang_Nga_Bay', 'B'), ('Similan_Islands', 'B'), ('Khao_Lak', 'B'), ('Ko_Tapu', 'B'), ('Mu_Ko_Surin_National_Park', 'B'), ('Khao_Lak-Lam_Ru_National_Park', 'N')],
    'พัทลุง': [('Thale_Noi_Waterbird_Park', 'N'), ('Khao_Pu-Khao_Ya_National_Park', 'N'), ('Tham_Malai', 'N')],
    'พิจิตร': [('Bueng_Si_Fai', 'N'), ('Wat_Tha_Luang', 'T')],
    'พิษณุโลก': [('Wat_Phra_Si_Rattana_Mahathat_(Phitsanulok)', 'T'), ('Phu_Hin_Rong_Kla_National_Park', 'N'), ('Thung_Salaeng_Luang_National_Park', 'N'), ('Sergeant_Major_Thawee_Folk_Museum', 'M'), ('Wat_Chula_Mani', 'T'), ('Sakunothayan_Waterfall', 'N')],
    'เพชรบุรี': [('Phra_Nakhon_Khiri', 'H'), ('Kaeng_Krachan_National_Park', 'N'), ('Cha-am', 'B'), ('Phra_Ram_Ratchaniwet', 'M'), ('Wat_Mahathat_Worawihan_(Phetchaburi)', 'T'), ('Tham_Khao_Luang', 'N')],
    'เพชรบูรณ์': [('Khao_Kho', 'N'), ('Nam_Nao_National_Park', 'N'), ('Phu_Thap_Boek', 'N'), ('Wat_Phra_That_Pha_Son_Kaew', 'T')],
    'แพร่': [('Wat_Phra_That_Cho_Hae', 'T'), ('Phae_Mueang_Phi', 'N'), ('Mae_Yom_National_Park', 'N'), ('Vongburi_House', 'M'), ('Wat_Luang_(Phrae)', 'T')],
    'ภูเก็ต': [('Patong', 'B'), ('Big_Buddha_(Phuket)', 'T'), ('Wat_Chalong', 'T'), ('Phuket_Old_Town', 'A'), ('Karon_Beach', 'B'), ('Kata_Beach', 'B'), ('Promthep_Cape', 'A'), ('Surin_Beach', 'B'), ('Nai_Harn_Beach', 'B'), ('Sirinat_National_Park', 'N'), ('Naithon_Beach', 'B'), ('Phuket_FantaSea', 'A')],
    'มหาสารคาม': [('Phra_That_Na_Dun', 'T')],
    'มุกดาหาร': [('Phu_Pha_Thoep_National_Park', 'N'), ('Phu_Sa_Dok_Bua_National_Park', 'N'), ('Mukdahan_National_Museum', 'M'), ('Indochina_Market', 'K')],
    'แม่ฮ่องสอน': [('Pai,_Thailand', 'A'), ('Mae_Hong_Son', 'A'), ('Wat_Phra_That_Doi_Kong_Mu', 'T'), ('Tham_Lot', 'N'), ('Pang_Ung', 'N'), ('Mae_Surin_National_Park', 'N'), ('Ban_Rak_Thai', 'A'), ('Pai_Canyon', 'N'), ('Sri_Lanna_National_Park', 'N')],
    'ยโสธร': [('Phra_That_Anon', 'T')],
    'ยะลา': [('Betong', 'A'), ('Yala_Central_Mosque', 'T')],
    'ร้อยเอ็ด': [('Bueng_Phalan_Chai', 'N'), ('Wat_Burapha_Phiram', 'T'), ('Phra_Maha_Chedi_Chai_Mongkhon', 'T')],
    'ระนอง': [('Raksa_Warin_Hot_Spring', 'N'), ('Ngao_Mangrove_Forest', 'N'), ('Laem_Son_National_Park', 'N'), ('Ko_Phayam', 'B')],
    'ระยอง': [('Ko_Samet', 'B'), ('Khao_Laem_Ya-Mu_Ko_Samet_National_Park', 'B'), ('Ban_Phe', 'B'), ('Khao_Chamao-Khao_Wong_National_Park', 'N'), ('Ko_Man_Nok', 'B')],
    'ราชบุรี': [('Damnoen_Saduak_Floating_Market', 'K'), ('Khao_Ngu_Stone_Park', 'N'), ('Wat_Khanon_Nang_Yai', 'T')],
    'ลพบุรี': [('Phra_Prang_Sam_Yot', 'H'), ('Phra_Narai_Ratchaniwet', 'M'), ('San_Phra_Kan', 'T'), ('Wat_Phra_Si_Rattana_Mahathat_(Lopburi)', 'T'), ('Pa_Sak_Jolasid_Dam', 'A')],
    'ลำปาง': [('Wat_Phra_That_Lampang_Luang', 'T'), ('Thai_Elephant_Conservation_Center', 'A'), ('Chae_Son_National_Park', 'N'), ('Wat_Phra_Kaeo_Don_Tao', 'T'), ('Baan_Sao_Nak', 'M'), ('Wat_Si_Chum_(Lampang)', 'T')],
    'ลำพูน': [('Wat_Phra_That_Haripunchai', 'T'), ('Wat_Chamthewi', 'T'), ('Doi_Khun_Tan_National_Park', 'N'), ('Hariphunchai_National_Museum', 'M')],
    'เลย': [('Phu_Kradueng_National_Park', 'N'), ('Phu_Ruea_National_Park', 'N'), ('Chiang_Khan', 'A'), ('Phu_Luang_Wildlife_Sanctuary', 'N'), ('Phra_That_Si_Song_Rak', 'T')],
    'ศรีสะเกษ': [('Wat_Pa_Maha_Chedi_Kaew', 'T'), ('Khao_Phra_Wihan_National_Park', 'N'), ('Prasat_Ban_Samor', 'H'), ('Phu_Pha_Mok', 'N')],
    'สกลนคร': [('Phu_Phan_National_Park', 'N'), ('Phra_That_Choeng_Chum', 'T'), ('Nong_Han_(Sakon_Nakhon)', 'N')],
    'สงขลา': [('Hat_Yai', 'A'), ('Samila_Beach', 'B'), ('Songkhla_Lake', 'N'), ('Songkhla_National_Museum', 'M'), ('Khao_Tang_Kuan', 'A'), ('Ko_Yo', 'A'), ('Ton_Nga_Chang_Wildlife_Sanctuary', 'N')],
    'สตูล': [('Tarutao_National_Park', 'B'), ('Ko_Lipe', 'B'), ('Ko_Tarutao', 'B'), ('Thale_Ban_National_Park', 'N'), ('Ko_Adang', 'B'), ('Ko_Bulon_Lae', 'B')],
    'สมุทรปราการ': [('Ancient_City_(Thailand)', 'M'), ('Erawan_Museum', 'M'), ('Phra_Samut_Chedi', 'T'), ('Phra_Chulachomklao_Fort', 'H'), ('Bang_Pu', 'B')],
    'สมุทรสงคราม': [('Amphawa', 'K'), ('Maeklong_Railway_Market', 'K'), ('Wat_Bang_Kung', 'T'), ('Rama_II_Memorial_Park', 'M'), ('Don_Hoi_Lot', 'N')],
    'สมุทรสาคร': [('Khlong_Khon', 'N'), ('Wat_Yai_Chom_Prasat', 'T')],
    'สระแก้ว': [('Pang_Sida_National_Park', 'N'), ('Ta_Phraya_National_Park', 'N'), ('Aranyaprathet', 'K'), ('Rong_Kluea_Market', 'K'), ('Prasat_Sdok_Kok_Thom', 'H')],
    'สระบุรี': [('Phra_Phutthabat', 'T'), ('Namtok_Sam_Lan_National_Park', 'N'), ('Khao_Chin_Lae', 'N')],
    'สิงห์บุรี': [('Bang_Rachan', 'H'), ('Wat_Phra_Non_Chaksi', 'T')],
    'สุโขทัย': [('Sukhothai_Historical_Park', 'H'), ('Si_Satchanalai_Historical_Park', 'H'), ('Wat_Mahathat_(Sukhothai)', 'T'), ('Wat_Si_Chum', 'T'), ('Wat_Sa_Si', 'T'), ('Wat_Si_Sawai', 'T'), ('Wat_Traphang_Ngoen', 'T'), ('Wat_Chang_Lom', 'T'), ('Ramkhamhaeng_National_Museum', 'M'), ('Wat_Phra_Si_Rattana_Mahathat_(Chaliang)', 'T'), ('Wat_Chedi_Chet_Thaeo', 'T')],
    'สุพรรณบุรี': [('Don_Chedi_Monument', 'A'), ('Wat_Pa_Lelai_Worawihan', 'T'), ('U_Thong_National_Museum', 'M'), ('Bueng_Chawak', 'N'), ('Sam_Chuk_Market', 'K')],
    'สุราษฎร์ธานี': [('Ko_Samui', 'B'), ('Ko_Pha_Ngan', 'B'), ('Ko_Tao', 'B'), ('Khao_Sok_National_Park', 'N'), ('Cheow_Lan_Lake', 'N'), ('Ang_Thong_National_Marine_Park', 'B'), ('Wat_Phra_Borommathat_Chaiya', 'T'), ('Big_Buddha_Temple_(Ko_Samui)', 'T'), ('Chaweng', 'B'), ('Hin_Ta_and_Hin_Yai_Rocks', 'A'), ('Lamai', 'B')],
    'สุรินทร์': [('Prasat_Sikhoraphum', 'H'), ('Prasat_Ta_Muen_Thom', 'H'), ('Prasat_Ta_Muan', 'H'), ('Ban_Ta_Klang', 'A')],
    'หนองคาย': [('Sala_Keoku', 'M'), ('Wat_Phra_That_Bang_Phuan', 'T'), ('Thai-Lao_Friendship_Bridge', 'A'), ('Wat_Pho_Chai_(Nong_Khai)', 'T'), ('Tha_Sadet_Market', 'K')],
    'หนองบัวลำภู': [('Tham_Erawan', 'N'), ('Phu_Kao-Phu_Phan_Kham_National_Park', 'N'), ('Wat_Tham_Pha_Daen', 'T')],
    'อ่างทอง': [('Wat_Muang', 'T'), ('Wat_Chaiyo_Worawihan', 'T')],
    'อำนาจเจริญ': [('Phu_Sa_Dok_Bua', 'N'), ('Phra_That_Phra_Mongkol_Ming_Mueang', 'T')],
    'อุดรธานี': [('Ban_Chiang_Archaeological_Site', 'H'), ('Nong_Han_Kumphawapi', 'N'), ('Phu_Phra_Bat_Historical_Park', 'H'), ('Phu_Foi_Lom', 'N')],
    'อุตรดิตถ์': [('Sirikit_Dam', 'A'), ('Phu_Soi_Dao_National_Park', 'N'), ('Wat_Phra_Borommathat_Thung_Yang', 'T')],
    'อุทัยธานี': [('Huai_Kha_Khaeng_Wildlife_Sanctuary', 'N'), ('Wat_Tha_Sung', 'T'), ('Sakae_Krang_River', 'N')],
    'อุบลราชธานี': [('Pha_Taem_National_Park', 'N'), ('Wat_Nong_Pah_Pong', 'T'), ('Sam_Phan_Bok', 'N'), ('Kaeng_Tana_National_Park', 'N'), ('Wat_Phra_That_Nong_Bua', 'T'), ('Phu_Chong-Na_Yoi_National_Park', 'N'), ('Khong_Chiam_District', 'A'), ('Wat_Thung_Si_Mueang', 'T')],
}

if __name__ == "__main__":
    n = sum(len(v) for v in SEED.values())
    print(len(SEED), "จังหวัด", n, "ชื่อบทความ")


# ---- ภาคเหนือ: รายการตั้งต้นเพิ่ม (ชื่อบทความ en.wikipedia ที่ใช้เป็นกุญแจค้นเท่านั้น) ----
# ชื่อที่หาไม่เจอหรือไม่มีพิกัดจะถูกข้ามและรายงานใน docs/COVERAGE.md ตอนรัน build_places.py
NORTH_EXTRA = {   # ทุกชื่อตรวจแล้วว่ามีบทความ+พิกัดอยู่ในจังหวัดนั้นจริง (2026-11-01)
    "เชียงราย": [("Chiang_Saen", "H"), ("Khun_Chae_National_Park", "N"), ("Lam_Nam_Kok_National_Park", "N"), ("Tham_Luang_Nang_Non", "N")],
    "ลำปาง": [("Ratsadaphisek_Bridge", "A"), ("Mae_Wa_National_Park", "N")],
    "ลำพูน": [("Wat_Phra_Phutthabat_Tak_Pha", "T")],
    "แม่ฮ่องสอน": [("Salawin_National_Park", "N")],
    "น่าน": [("Khun_Nan_National_Park", "N"), ("Mae_Charim_National_Park", "N"), ("Phu_Fa_waterfall", "N")],
    "พะเยา": [("Doi_Luang_National_Park", "N")],
    "แพร่": [("Wiang_Kosai_National_Park", "N"), ("Lam_Nam_Nan_National_Park", "N"), ("Tham_Pha_Nang_Khoi", "N")],
    "อุตรดิตถ์": [("Ton_Sak_Yai_National_Park", "N")],
}
for _prov, _items in NORTH_EXTRA.items():
    _have = {t for t, _ in SEED.get(_prov, [])}
    SEED[_prov] = SEED.get(_prov, []) + [x for x in _items if x[0] not in _have]


# ---- ภาคตะวันออกเฉียงเหนือ: รายการเพิ่มที่ตรวจแล้ว (2026-11-01) ----
NE_EXTRA = {
    "กาฬสินธุ์": [("Phu_Pha_Lek_National_Park", "N")],
    "ขอนแก่น": [("Phra_That_Kham_Kaen", "T"), ("Phra_Mahathat_Kaen_Nakhon", "T")],
    "นครราชสีมา": [("Prasat_Phanom_Wan", "H"), ("Wat_Thammachak_Semaram", "T")],
    "บึงกาฬ": [("Phu_Thok", "T")],
    "เลย": [("Phu_Suan_Sai_National_Park", "N")],
    "ศรีสะเกษ": [("Prasat_Sa_Kamphaeng_Yai", "H")],
    "อุดรธานี": [("Wat_Kham_Chanot", "T"), ("Wat_Pa_Phu_Kon", "T")],
    "อำนาจเจริญ": [("Wat_Phra_Lao_Thep_Nimit", "T"), ("Wat_Tham_Saeng_Phet", "T")],
    "มหาสารคาม": [("Wat_Photharam,_Maha_Sarakham", "T")],
    "ร้อยเอ็ด": [("Luangpho_Yai", "T")],
}
for _prov, _items in NE_EXTRA.items():
    _have = {t for t, _ in SEED.get(_prov, [])}
    SEED[_prov] = SEED.get(_prov, []) + [x for x in _items if x[0] not in _have]
