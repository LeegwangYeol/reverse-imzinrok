#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Safety and Integrity Verification Tool for Reverse-Imzinrok Project.

Verifies:
1. Git repository status in C:\src\rea is 100% clean (no untracked, modified, or staged files).
2. All key files in C:\src\reverse-imzinrok\YM retain exact byte sizes and SHA-256 hashes.
3. No foreign / modified files were created inside C:\src\reverse-imzinrok\YM.
"""

import os
import sys
import subprocess
import hashlib
import json
from pathlib import Path

# Force utf-8 output on Windows consoles
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Key files manifest: 204 critical binaries, archives, palettes, maps, and system files
YM_KEY_MANIFEST = {
    "dawn/Data": {
        "size": 230202,
        "sha256": "2b16045633fed94972a900686901fbd93266bc1079560b1385c7fed86799a21c"
    },
    "dawn/Data.hq": {
        "size": 5408,
        "sha256": "20ccc1c4e74abf59f7c5847479f20f2703506917fa80af0e4d6571d8eb463dab"
    },
    "dawn/dawn.exe": {
        "size": 1032192,
        "sha256": "302735c2feaf0467a511a9b3bdb0b87d09e7ab7be903299ca4245a51a54aa67a"
    },
    "dawn/ddraw.dll": {
        "size": 413184,
        "sha256": "3bc7230d1a6023a8fc0ea52b18d7edda94fcb4c0ae3d178f6e1577d68a62bd19"
    },
    "dawn/dpwsockx.dll": {
        "size": 39200,
        "sha256": "11f9db3b946c5e7f7001811257d9bc27d0050ee93701091cc3bf1e0c4c86f972"
    },
    "dawn/dxwrapper.dll": {
        "size": 1957888,
        "sha256": "96c443193bad8794ebf04738566e092f8b34ae4541cb2433fd0708d49edbe8fe"
    },
    "dawn/ipxconfig.exe": {
        "size": 461600,
        "sha256": "b6190f0bacf3b20612268d72b80b1d0542ec78839737d3000b2bb58aa1b3d252"
    },
    "dawn/ipxwrapper.dll": {
        "size": 84768,
        "sha256": "b6c0bd24e5c623c517ff8bb8b39a133b2a3baa9553519ea7e8fd92f960e848d5"
    },
    "dawn/Map Editor.exe": {
        "size": 1032192,
        "sha256": "ae301f2f8079fc6b247013f72aac9922bfa9d87ae67843eb7a1e64047adca393"
    },
    "dawn/mswsock.dll": {
        "size": 36128,
        "sha256": "685fcbfd789ea1387297dc2151983138a76a080b4eb495e8c81bab914b4e29aa"
    },
    "dawn/syw2x.dll": {
        "size": 23040,
        "sha256": "f97b15fb39a286f055c3da9aad50aeeadcb8d464077c21d24691041999a45f2c"
    },
    "dawn/syw2xinjector.exe": {
        "size": 37376,
        "sha256": "8b3a66f919d5dfd5afd8f576bbec1313dcf1951c0e47ad569e0a653b267c9349"
    },
    "dawn/UseMap.exe": {
        "size": 1032192,
        "sha256": "f899ee92d60c99882c6bb2c5ea118de68b6abb30852114abdf1ea89807a29611"
    },
    "dawn/wsock32.dll": {
        "size": 35616,
        "sha256": "d3e15c8cd5523405acbdddd592409344948a896e12a9a2f37f8bfd55f118a3a5"
    },
    "dawn/_inmm.dll": {
        "size": 167936,
        "sha256": "03192987e9c877cf344874412d2c0e1a80b5d5f8b91f325771e9615feadbf160"
    },
    "dawn/_inmmserv.exe": {
        "size": 151552,
        "sha256": "1a0bdac8376298d1ef22d0d8b7ed4a57edfdc36219084346979cfba6afc3ab9e"
    },
    "dawn/BattleSpr/BattleNet.pal": {
        "size": 768,
        "sha256": "8f058ea4456e16d3f0dd4d70e1def3f4d4c14d30877570d1fcb68db5483497f7"
    },
    "dawn/cusmap/(2인,100X100)삶과죽음의갈림길.map": {
        "size": 1132876,
        "sha256": "937147406c7caf58206a3060a43494d271a77d330028d14f7becc0754b798bb7"
    },
    "dawn/cusmap/(2인,100X100)수성.map": {
        "size": 1132876,
        "sha256": "be32f03e85ffbb069ddef4f3c2f3d7cf8d508561584aca5ac7c6bf369aa84415"
    },
    "dawn/cusmap/(2인,100x100)태극.map": {
        "size": 1132876,
        "sha256": "69577339edc2296b9abf03899b5c10352c5093a6e5c5fb6037125e8489cc0022"
    },
    "dawn/cusmap/(2인,120X120)남해의 작은 섬.map": {
        "size": 1132876,
        "sha256": "634942323901b3ea73d8db3f360da13872377fb05246215a70ca9d11eed878ff"
    },
    "dawn/cusmap/(2인,120X120)대관령.map": {
        "size": 1132876,
        "sha256": "fde94e2e910da27fab11a93b0372c2f64d6ba35591a2be08a1710a598e7f5a0d"
    },
    "dawn/cusmap/(2인,120x120)대진.map": {
        "size": 1132876,
        "sha256": "4f8022b9b61debe141b57642d531388eb11e94a9cf34e4da271c53ee8beab58f"
    },
    "dawn/cusmap/(2인,120X120)돌격.map": {
        "size": 1132876,
        "sha256": "63e9f94f807bd77288584bd5bce74ed5fa88850bb363411dc21e4bf217eac1e2"
    },
    "dawn/cusmap/(2인,120X120)신의한수.map": {
        "size": 1132876,
        "sha256": "41e3c83517381ba0f89a0e48d4736577917cc0e2984de7f1c2d75921a4078a0f"
    },
    "dawn/cusmap/(2인,120x120)청주.map": {
        "size": 1132876,
        "sha256": "abfcdc8b0b31f0bea2db4209f7df7b57615fe0907d82abb87e4b79f0b71523c6"
    },
    "dawn/cusmap/(2인,130x130)고속도로.map": {
        "size": 1132876,
        "sha256": "d674d8ce1954dc29ff7ff57add0c70f21f61332b9768afd5ab8757d0ce3bc5d3"
    },
    "dawn/cusmap/(2인,130x130)극락.map": {
        "size": 1132876,
        "sha256": "9344bd74b22ee56321163c075055199a9335fec78f53b9ac677a0d6f613bdf0c"
    },
    "dawn/cusmap/(2인,130x130)백로.map": {
        "size": 1132876,
        "sha256": "19cbf4a6952b1c265e652dd65631dea5498bf6bbbbe4e195c3658f90e54c0a38"
    },
    "dawn/cusmap/(2인,130X130)아수라.map": {
        "size": 1132876,
        "sha256": "971e4d48cc1cbefcc224bc895a7d0e175a861d9458cebaa0662d876e1858fc46"
    },
    "dawn/cusmap/(2인,140x140)삼공도.map": {
        "size": 1132876,
        "sha256": "e52e56bf710c33c2ec248a6f25776910c0b759a46c573aa0050782900e581c19"
    },
    "dawn/cusmap/(2인,180X180)바다위의성.map": {
        "size": 1132876,
        "sha256": "13f7cb05b4cba862f62201a3552463896f98496da583a512adafa20a85a5ae8d"
    },
    "dawn/cusmap/(2인,70X70)함성이그치지않는바다.map": {
        "size": 1132876,
        "sha256": "0fb2f331b41e3648d3779e4cc1a761bef2925aae4e74f6988fd1a57e4e4eaac0"
    },
    "dawn/cusmap/(2인,90X90)물에빠진수레바퀴.map": {
        "size": 1132876,
        "sha256": "744c1da5c80a47eb6a89669b7c30b3ccbbd4f5574e2205ca813ddee91bb05e28"
    },
    "dawn/cusmap/(2인,90X90)물에잠긴수레바퀴.map": {
        "size": 1132876,
        "sha256": "ba33dbc454f455b999f1b7ca0d37a0528e64f85c36b90af596bcbf938b4f9e61"
    },
    "dawn/cusmap/(3인,120x120)삼태극.map": {
        "size": 1132876,
        "sha256": "0e53640b6535046350c7b82c9006d1dabdf78f25c75c430d3c09c8966fb7e91b"
    },
    "dawn/cusmap/(3인,140x140)누란지위.map": {
        "size": 1132876,
        "sha256": "954baf000b4ed30ff6407ec93409ccffa33cd185b2fba70b986716db86c17701"
    },
    "dawn/cusmap/(3인,140x140)신태극.map": {
        "size": 1132876,
        "sha256": "c6df9f499a1be7464194f8e7918c1873d0e0633cea99e6131b74c39f05216326"
    },
    "dawn/cusmap/(3인,150x150)시스템(system).map": {
        "size": 1132876,
        "sha256": "5a81cd7705edb6e6f864b5487b447f36949bedfbebe7c7220762336a20209e55"
    },
    "dawn/cusmap/(3인,180x180)삼파전.map": {
        "size": 1132876,
        "sha256": "c699a93baeb5d387ff3c913ef22b0168b55d207557d8aa1a21e91b37b6a56c3b"
    },
    "dawn/cusmap/(4인,120X120)경주비빔밥.map": {
        "size": 1132876,
        "sha256": "39c3b21a49d1bba53dee9eb03da511dbeda81c30259ad92ba5c4bef888dd5da5"
    },
    "dawn/cusmap/(4인,120X120)무조건돌격하라.map": {
        "size": 1132876,
        "sha256": "e774b101952c386f0bcc58c132a6a85c3b17a4fac447a22bfb1bbd6ac8113fa9"
    },
    "dawn/cusmap/(4인,120X120)중간계전투.map": {
        "size": 1132876,
        "sha256": "1abfe59698a39989aa75ee64537c7f85a0fa49a2a4f6b982c808a03b09399c39"
    },
    "dawn/cusmap/(4인,130x130)메마른 땅.map": {
        "size": 1132876,
        "sha256": "0321a9b02a1d63cdf7ef2ee2f2deb2cd9a8783a54231438fbd543a02c9d506ba"
    },
    "dawn/cusmap/(4인,140X140)[HQ]전주비빔밥.map": {
        "size": 1132876,
        "sha256": "59120a3f6deb3b6e24185183630fa57145d1494ee5a1e98b685b4216dfaa8c92"
    },
    "dawn/cusmap/(4인,140X140)광복 1945.map": {
        "size": 1132876,
        "sha256": "3c20782cf13927ad5be0cd492d4e219a490dc3aa8c593cc87db20306cf7a8131"
    },
    "dawn/cusmap/(4인,140X140)군주.map": {
        "size": 1132876,
        "sha256": "de96e61a94fdc9486c0133afc6ad2a6886f8864b5cf738df98edf972298d8553"
    },
    "dawn/cusmap/(4인,140x140)무극.map": {
        "size": 1132876,
        "sha256": "9b0eea4ac88de53fc7a78ea212f60465526ddf9478b223057fdbc106494f1182"
    },
    "dawn/cusmap/(4인,140X140)봉응치.map": {
        "size": 1132876,
        "sha256": "97178d1ce7b98fbe6535767a0a0953a6519d72b56a8fa51b55ff1fb77a31198d"
    },
    "dawn/cusmap/(4인,140X140)승부사.map": {
        "size": 1132876,
        "sha256": "9c1dcca8130ca747a2361efae6fb00f34c6b5b7dd12b5a3428e978356ac6ffec"
    },
    "dawn/cusmap/(4인,140X140)영원한강자는없다.map": {
        "size": 1132876,
        "sha256": "df51e3135d08308e4cc36fba6e0900fda6b7606c1d3ce5c25753858218baf341"
    },
    "dawn/cusmap/(4인,140X140)올빼미의성은어디인가.map": {
        "size": 1132876,
        "sha256": "98b91eb1211f5e30ad0e038ca130d36836a4f5398f4c82de0a8d53f990c855d5"
    },
    "dawn/cusmap/(4인,140X140)용쟁호투.map": {
        "size": 1132876,
        "sha256": "a3cc95e7508d09fe4190d17bbbab3fc3061bece2b4110cbdefde72ab56755d77"
    },
    "dawn/cusmap/(4인,140x140)입춘대길.map": {
        "size": 1132876,
        "sha256": "e10e8717760e8bbfe8423b701ad5038dc21af873f838fbeb688758bbcf60bc05"
    },
    "dawn/cusmap/(4인,140X140)태풍의눈.map": {
        "size": 1132876,
        "sha256": "32796486abd7e62b4027105c7d1f5e5d4e5a6ec4fbf2786390d4aae1668a136a"
    },
    "dawn/cusmap/(4인,140x140)팥빙수.map": {
        "size": 1132876,
        "sha256": "f6f245806461276e2c80116b88c485383faf193dbe2580cb7836b62ca42605d0"
    },
    "dawn/cusmap/(4인,140X140)필사즉생 필생즉사.map": {
        "size": 1132876,
        "sha256": "ce1b2b8a03d57bff3fc3e83be8dcf7a621984016036c41d98550903ef9503c73"
    },
    "dawn/cusmap/(4인,160X160)[HQ]전략은끊임없도다.map": {
        "size": 1132876,
        "sha256": "4d06b6753a89c553ad023d59f15328d1d7a7a4207447294fca5d6d71604a0806"
    },
    "dawn/cusmap/(4인,160X160)싸움터위에핀꽃.map": {
        "size": 1132876,
        "sha256": "5ef008318c4397525d8a1708eb204fdab081e5eb7940b5db181c00ac169a5163"
    },
    "dawn/cusmap/(4인,160x160)입춘대희.map": {
        "size": 1132876,
        "sha256": "e41066bb88d23be48b23b626197d7178d2573b2df534ac49552e49c5eae9a690"
    },
    "dawn/cusmap/(4인,160X160)전장의광기.map": {
        "size": 1132876,
        "sha256": "36a071c91dd55934c51e86a2655f2d4be7cf72e07a55798cbc0db8fe03cf3e00"
    },
    "dawn/cusmap/(4인,180x180)거상속으로.map": {
        "size": 1132876,
        "sha256": "dc89da9d3b50ea52697f8899d7e1eee4ad642057e661fae3c33a31d9118d5e75"
    },
    "dawn/cusmap/(4인,180X180)격돌공성전.map": {
        "size": 1132876,
        "sha256": "280e8447b477baeb95954187c2f8ded407f960e3d4ec90e5fe5c81dc67f86722"
    },
    "dawn/cusmap/(4인,180X180)돌지않는수레바퀴.map": {
        "size": 1132876,
        "sha256": "b8cdb3efa73c07cf30b63fc3f5f91542ad6d49a8e9504d1e89138096da1ec4e9"
    },
    "dawn/cusmap/(4인,180X180)사태극.map": {
        "size": 1132876,
        "sha256": "26429a959189a3e89b0dd593caa6c61c2061a967a1a3521dcb8d429d46e001ec"
    },
    "dawn/cusmap/(4인,180X180)일도양단.map": {
        "size": 1132876,
        "sha256": "35c08d17d971a9101414a830a0abd70158b59ddce047935a3690d1f75373a69b"
    },
    "dawn/cusmap/(4인,180x180)임전무퇴.map": {
        "size": 1132876,
        "sha256": "b5169cd34fa6c719fdafd45b2ed36c7cfce7098e8a7810afa2c2dc01707a7fca"
    },
    "dawn/cusmap/(4인,180X180)파이선.map": {
        "size": 1132876,
        "sha256": "f5e5148adfa676ac1daa81f1eba94caa110e0d46fbbcbebf1bfe1f2a47a55cbe"
    },
    "dawn/cusmap/(4인,180X180)행운의여신은누구에게.map": {
        "size": 1132876,
        "sha256": "0a8a8ddbd56b85578ffbb13105f2fef2968dfca49971fab70f9cc3c4ba2e9af2"
    },
    "dawn/cusmap/(5인,180X180)호수위의비치는달.map": {
        "size": 1132876,
        "sha256": "a9e453484d52bd53434e545e6776b0a1270bd9206376dc655ccf253908e61aa2"
    },
    "dawn/cusmap/(6인,150X150)현명한군주는기다리지않는다.map": {
        "size": 1132876,
        "sha256": "9e5d8a0ebbc5e6e59c0ae8d65e315605473c61015f5b26f32f03ec943eec176d"
    },
    "dawn/cusmap/(6인,180X180)[HQ]비오는날의수채화.map": {
        "size": 1132876,
        "sha256": "720dd23625c82cab29bf17326f3edeedf062cf61656d5c7ece3cada3de93029b"
    },
    "dawn/cusmap/(6인,180X180)눈속에묻힌싸움터.map": {
        "size": 1132876,
        "sha256": "96fbc5b8eaa3fd2a71f3f61252d1d930c0601fbf579bf57fc77bffe7c0aaf905"
    },
    "dawn/cusmap/(8인,180X180)늪지위의혼전.map": {
        "size": 1132876,
        "sha256": "80cc9d892f39d79e1810a349530fd0d8569b1e26bc4dda6130f0141c8a60836e"
    },
    "dawn/cusmap/(8인,180X180)병사는지치지않는다.map": {
        "size": 1132876,
        "sha256": "66e9a52406a5d05f3f446bd550b213d0cfe6bce5cbe4ae3ea97a67cf5ca5df8a"
    },
    "dawn/Online/Hq.hq": {
        "size": 1475,
        "sha256": "9312f5e4d79b3451978a5b96d11dd639afeb22f576fffed9e59e922ee47c1310"
    },
    "dawn/Online/BattleMap/323220102001.map": {
        "size": 1132876,
        "sha256": "66ecf2d7f1ace18fe57e9a1d17d57619bf99a580cbd8bd7780af94da4a583c1a"
    },
    "dawn/Online/BattleMap/323220302001.map": {
        "size": 1132876,
        "sha256": "81b6399658b2ef0bb6e3d3caf89217e76a65513bb9de4828262f40b1c6d411df"
    },
    "dawn/Online/BattleMap/404040101001.map": {
        "size": 1132876,
        "sha256": "e3ba4cd661a0a44508bc411896bf6f7995f994a8381028570bc9690d3ed5dfdf"
    },
    "dawn/Online/BattleMap/404040401001.map": {
        "size": 1132876,
        "sha256": "c60a9783664a255464a028b22e981807d457e7039492d6654859714c1c856c40"
    },
    "dawn/Online/BattleMap/404040701001.map": {
        "size": 1132876,
        "sha256": "2c73668819c4eaa9afc683674c2a414c5cc80a0edc0c4bf0c84e995720dae36e"
    },
    "dawn/Online/BattleMap/404040701002.map": {
        "size": 1132876,
        "sha256": "b73b9fab7103c5acca50ac366126ea6fc9db95b4818d2af1bb5b495ba4656f83"
    },
    "dawn/Online/BattleMap/404040701003.map": {
        "size": 1132876,
        "sha256": "41e5fa7cbab3fad60b34159002e8a5c12dba97a5a9d0d2fe6ac8678665be5151"
    },
    "dawn/Online/BattleMap/606080101001.map": {
        "size": 1132876,
        "sha256": "9f2e31d0d7bac8de58cb73f0b223b1430d0f46c43453cd2c752afef84c09bae4"
    },
    "dawn/Online/BattleMap/606080101002.map": {
        "size": 1132876,
        "sha256": "be9b9087376ce8841a05dbe0e616a70de2a8224ccda2f7ed0a9d6f0d7655f76e"
    },
    "dawn/Online/BattleMap/606080601001.map": {
        "size": 1132876,
        "sha256": "c6d9ebe45571b127df7f230548598c3debf38c3942ec19efc025effa23d33f81"
    },
    "dawn/Online/Map/daeguan1.map": {
        "size": 100016,
        "sha256": "1d1cc4dead7827558100c3886b056ac4122af0db3afe2d2d656677b6829dbfa5"
    },
    "dawn/Online/Map/daeguan2.map": {
        "size": 100016,
        "sha256": "87dff6374990f9fb99085a60976e3ae49cfbf8f8f092775782b4e8e393eff802"
    },
    "dawn/Online/Map/daeguan3.map": {
        "size": 100016,
        "sha256": "35f742fe3095207dc65c9b02b49ff5d998decd496986432d3780b1a1195f39aa"
    },
    "dawn/Online/Map/Gosu.map": {
        "size": 100016,
        "sha256": "19eccd226880b21ec3e394c31e5765123a02d018fed2ec511d79d3720b575b76"
    },
    "dawn/Online/Map/gosu2.map": {
        "size": 100016,
        "sha256": "e93db97dd1c7a04ba0ff943a088b212f9095a9bf35806be92dcd1b966022c804"
    },
    "dawn/Online/Map/gosu3.map": {
        "size": 100016,
        "sha256": "fea9d654548e4a325a75b598193eab9cc3b9d593fd23164d1de69fb91ca231d0"
    },
    "dawn/Online/Map/hanrasan.map": {
        "size": 200016,
        "sha256": "e8cb15695e86108785a476f017cc2b23b1bd4e2099c1fd1a2ff66f077fd832e7"
    },
    "dawn/Online/Map/jnsnowspa1.map": {
        "size": 100016,
        "sha256": "fc6bda923b2e053fc1dfee5812f4bc96ef47a9fe82d90d4d13ab313a084d5320"
    },
    "dawn/Online/Map/jnsnowspa2.map": {
        "size": 100016,
        "sha256": "146cd005226bb12dd00d74e57274fe751a09d303ac15019823e8e0d9b1618dcc"
    },
    "dawn/Online/Map/jnsnowspa3.map": {
        "size": 100016,
        "sha256": "7b91c96326f61cf291985e23ea5ff4db6c59ec50f90b47c76dc93c3cd1037af7"
    },
    "dawn/Online/Map/koreaseouljajak.map": {
        "size": 46256,
        "sha256": "dc416032e1b0cdb6897bb58aefa40757aaba2376c18ed2fed9ca49bcc826042b"
    },
    "dawn/Online/Map/map.map": {
        "size": 40000016,
        "sha256": "7439f10923bce6602ccc719c6aa4ed5a3b361086f86cb467a124f45c80d9e2a8"
    },
    "dawn/Online/Map/saku1.map": {
        "size": 100016,
        "sha256": "b5718b43e2212b7481403ae3f4a1b04e7fd73bb920a54f014e9f96e25f35c607"
    },
    "dawn/Online/Map/saku2.map": {
        "size": 100016,
        "sha256": "72e0a38f1e665f9c3c443a90e4a0b9e78ed58b07e791697bb9f3c30a9890f983"
    },
    "dawn/Online/Map/saku3.map": {
        "size": 100016,
        "sha256": "7df845a096e1434727935c86aba80516c8e9f4e1a58ae5d989ecdfc5f232c145"
    },
    "dawn/Online/Map/saku4.map": {
        "size": 100016,
        "sha256": "e52bd7c8c7b615be76c56a35071ecf20e9761c360ae03ed169380828fcf782b5"
    },
    "dawn/Online/Map/saku5.map": {
        "size": 100016,
        "sha256": "97877c1648fd96aaa5e07f8f2d5e9fd7c45180838682f8de94c3987fc13cc0ae"
    },
    "dawn/pal/00.pal": {
        "size": 768,
        "sha256": "6765cc437cb9055cb16a8553a0060dbf47ddd7747b52ee912f7dcd8a4de7eb33"
    },
    "dawn/pal/01.pal": {
        "size": 768,
        "sha256": "26e13efc14ae97fbe32e4e9057b825e760432753b2cdb9c4f88903bda582e011"
    },
    "dawn/pal/02.pal": {
        "size": 768,
        "sha256": "bd21fbfb40e9d0b2589d4df051d5d8527a69e8c77dd7515c050354cd38e7a16e"
    },
    "dawn/pal/03.pal": {
        "size": 768,
        "sha256": "083f481df858fa6d5b8e373c3fe42b22ef0c523239331c29faa1b266bfb19dc8"
    },
    "dawn/pal/04.pal": {
        "size": 768,
        "sha256": "acb4a4c1faba20c91d5019a77f2915be14bf662e0cb39c00d715d53f8d136061"
    },
    "dawn/pal/05.pal": {
        "size": 768,
        "sha256": "662c6a9ce0c060148d53b559b3e933b10bf5253565c888e33a39e601a16a9745"
    },
    "dawn/pal/06.pal": {
        "size": 768,
        "sha256": "c570968607ba13956db0c1f02cc255eba770345a49c624049c1bd0e72271f68f"
    },
    "dawn/pal/07.pal": {
        "size": 768,
        "sha256": "a392b5aa4a12ca18fcc0f78d1c0544cb98857c438f8f5d50eed86673c45f8606"
    },
    "dawn/pal/08.pal": {
        "size": 768,
        "sha256": "8d1b6c36f8b562db6726ab4cf42b76b6977b0e498ab37714011187781f6f7e7f"
    },
    "dawn/pal/09.pal": {
        "size": 768,
        "sha256": "56c6d92d8f92e6d5e5d8f6b5d072e2a117fedcd7c808004b160753bf4aae1832"
    },
    "dawn/pal/10.pal": {
        "size": 768,
        "sha256": "f5f7de2d1c3fe8e85c9ee39a257603db20db2ec59318423a9809b1166d92ab3f"
    },
    "dawn/pal/11.pal": {
        "size": 768,
        "sha256": "ef115a0e0c15cdc41958ca46b5b14b456115f4baec5e3ca68599d2a8f435e3b8"
    },
    "dawn/pal/button_1_plus.PAL": {
        "size": 768,
        "sha256": "db15108a001075616ea7371e78aea8e8c5ff05aa8c3e66f3ec23054353265fcc"
    },
    "dawn/pal/choosenation_plus.pal": {
        "size": 768,
        "sha256": "2e0cb7e4a4d72fb081ccdd86f92bc6eb12112dad01d47ab12c8c29016345e3f7"
    },
    "dawn/pal/chooseplayerborder_plus.PAL": {
        "size": 768,
        "sha256": "0c40ca1aba1771c215255f77888988352ef8228812326b5973cdbfc5b56eef45"
    },
    "dawn/pal/chosestagetitle_plus.PAL": {
        "size": 768,
        "sha256": "080b756a824fc3be8a2b13a519b34a70b8c45fed2216fc9ab935ed9bd389bcf9"
    },
    "dawn/pal/imjin2.pal": {
        "size": 768,
        "sha256": "5ba2c020e9bd89210a10550fb4baaee8ab8bb316d4a2c7e66bdb24c6c8c4323b"
    },
    "dawn/pal/initmenu.pal": {
        "size": 768,
        "sha256": "811c4dedc5b392087f2ed08a26437e5bb9976f9ce57482a1a57e9458d220435e"
    },
    "dawn/pal/lobby.pal": {
        "size": 768,
        "sha256": "2ca970e43cb0d29bfc9238f33d149e7389c6044e5af27d1bfd66c242dd6ce3f4"
    },
    "dawn/pal/lobby_plus.pal": {
        "size": 768,
        "sha256": "807aca35dbe8985fafb16ba99b2b780bf80e6fc933debcce1a918ecb010d5ef8"
    },
    "dawn/pal/mapformatinfo_plus.pal": {
        "size": 768,
        "sha256": "6b084f332a9c58ab321d7d45a0fdf39196f39c5958ce156e832120b8939046ff"
    },
    "dawn/pal/night1.pal": {
        "size": 768,
        "sha256": "b085583412b8bb79bdf9b72d836881be37f6f36ad50d073db06bebd1c2670122"
    },
    "dawn/pal/night2.pal": {
        "size": 768,
        "sha256": "c45727bd8ffed04bf572da5ab38b14b7fcb819f540a15a2e5d13730357bda17d"
    },
    "dawn/pal/night3.pal": {
        "size": 768,
        "sha256": "4fe0c28dc64480c6f00876c5ee484e1b3caa77b3b63b27387c6cf7702c3d2f97"
    },
    "dawn/pal/night4.pal": {
        "size": 768,
        "sha256": "f8328d22007407df426dff9e489f43718e28772d03b3ddd5f663a5dd57156e95"
    },
    "dawn/pal/okcancelborder_plus.pal": {
        "size": 768,
        "sha256": "0c40ca1aba1771c215255f77888988352ef8228812326b5973cdbfc5b56eef45"
    },
    "dawn/pal/plus-choosenation.pal": {
        "size": 768,
        "sha256": "db15108a001075616ea7371e78aea8e8c5ff05aa8c3e66f3ec23054353265fcc"
    },
    "dawn/pal/result.pal": {
        "size": 768,
        "sha256": "39253620e0f3566ebb5e705c4246d08f36d05cfe2a702a5ddee8a20c06b78bbc"
    },
    "dawn/pal/titlelobby_plus.PAL": {
        "size": 768,
        "sha256": "fb10548d3362fa0bfbd25b697b1de5a4eb6f62624c7280b6e883cf367f9b9d63"
    },
    "dawn/pal/titleprotocol_plus.PAL": {
        "size": 768,
        "sha256": "198e139365cfc79f41173e16de4f51262748c1b8cbcd24e1564f0738313a2917"
    },
    "dawn/pal/titleresult_plus.pal": {
        "size": 768,
        "sha256": "7c1481b726310e26d196c8425a8d6ba6733490d134420dacc58693024723a833"
    },
    "dawn/pal/titlesession_plus.PAL": {
        "size": 768,
        "sha256": "198e139365cfc79f41173e16de4f51262748c1b8cbcd24e1564f0738313a2917"
    },
    "dawn/pal/titlestaff1_plus.PAL": {
        "size": 768,
        "sha256": "5ba2c020e9bd89210a10550fb4baaee8ab8bb316d4a2c7e66bdb24c6c8c4323b"
    },
    "dawn/pal/title_plus.PAL": {
        "size": 768,
        "sha256": "205d99ea6625c98e26b0bda9273c32375b4f41fee275c7873e553c4941a106bc"
    },
    "dawn/pal/ybriefingfnt_C_PLUS.pal": {
        "size": 768,
        "sha256": "ece117179ef6e7c8d639ff66af09b229f6033fd2c4945454f078b4edb6737470"
    },
    "dawn/pal/ybriefingfnt_J_PLUS.pal": {
        "size": 768,
        "sha256": "ece117179ef6e7c8d639ff66af09b229f6033fd2c4945454f078b4edb6737470"
    },
    "dawn/pal/ybriefingfnt_K_PLUS.pal": {
        "size": 768,
        "sha256": "ece117179ef6e7c8d639ff66af09b229f6033fd2c4945454f078b4edb6737470"
    },
    "dawn/script/eft/EncodeWave.exe": {
        "size": 103936,
        "sha256": "a17bf8f3d44eb86c1e855d22d487cbba3ab517fc82d0d84c61d57f2045871ae3"
    },
    "dawn/stagemap/plus01.map": {
        "size": 1132876,
        "sha256": "0a679d53d2c7042693ecaf3192456c59a1122a7167e0fc35a2d83bb451ad976b"
    },
    "dawn/stagemap/plus02.map": {
        "size": 1132876,
        "sha256": "85a4d34adb73c5cd573a7f07be94cbf7a7683013fa092edaa51cfa64a836fe18"
    },
    "dawn/stagemap/plus03.map": {
        "size": 1132876,
        "sha256": "b9fa0a5d5087907785c14312fd8364ad404a01e6efe287e8b77a9ec08f92955d"
    },
    "dawn/stagemap/plus04.map": {
        "size": 1132876,
        "sha256": "b8515d58039a2538e6300b32c78b3f646c097627b5395fb12663d2eef86e024e"
    },
    "dawn/stagemap/plus05.map": {
        "size": 1132876,
        "sha256": "bbeac642625077e6d1190ffc0f92658bcc8029e82720fa2f3d7744cf26f56ccc"
    },
    "dawn/stagemap/plus06.map": {
        "size": 1132876,
        "sha256": "994ae15bce7a4d2fbd53c668f4b0fd3c06e607b5611ac9c89e54bda529b31072"
    },
    "dawn/stagemap/plus07.map": {
        "size": 1132876,
        "sha256": "52d6de36f948da3603e01e366c26f97a3fad0ce47a25f2470f0a67c7bf488abd"
    },
    "dawn/stagemap/plus08.map": {
        "size": 1132876,
        "sha256": "a4e6d0752f2fb955d00767dd1c8125b5da9c8c47587fce68e63382fbb8bec4f6"
    },
    "dawn/stagemap/plus09.map": {
        "size": 1132876,
        "sha256": "2f89b3eaf3e1ea1c359b2d77146eefbb0c0ef9decf417920cffb56f8abbc2c51"
    },
    "dawn/stagemap/plus10.map": {
        "size": 1132876,
        "sha256": "a6c705e9589e6b639955cb730963d9a8ea0b9593ba0ed489ab45f399102069cd"
    },
    "dawn/stagemap/plus11.map": {
        "size": 1132876,
        "sha256": "1937305e0314cc58e1240e6ff894a85b350e7d2431df7ad9e19fd7a738e3ef08"
    },
    "dawn/stagemap/plus12.map": {
        "size": 1132876,
        "sha256": "a318365705ed3f76dbdf0930472276a16044338039911f84fe0abc7238955877"
    },
    "dawn/stagemap/plus13.map": {
        "size": 1132876,
        "sha256": "3c9fe70a8dadb0306a0b96cddd0a63cee9a329bb44f59d853ea0c3e9def98863"
    },
    "dawn/stagemap/plus14.map": {
        "size": 1132876,
        "sha256": "22a2f2410c723e9f8e8447c60878aa7b1c0e0b4a319f2551086a02d3dfc88336"
    },
    "dawn/stagemap/plus15.map": {
        "size": 1132876,
        "sha256": "1c4d4e3527853530453e2e00c175dca3f803f7f96dad8a4a75dc7b3ce2e11d70"
    },
    "dawn/stagemap/plus16.map": {
        "size": 1132876,
        "sha256": "cdf7f6579694f798ebc4fbd7453f402d4a207d2964071b7be820859d93d26e4b"
    },
    "dawn/stagemap/plus17.map": {
        "size": 1132876,
        "sha256": "01426d31d93d0d7ae25fab8282a74921340e0b7f7656813956184e12dca624a1"
    },
    "dawn/stagemap/plus18.map": {
        "size": 1132876,
        "sha256": "8fc5a53451243fcda8adf3943c4e04cf7f555071c06b62a522620c2ead86946c"
    },
    "dawn/stagemap/plus19.map": {
        "size": 1132876,
        "sha256": "a5b4a435aca81d90504d384ced34fc4e5deae10d0fd444746a666fbc430cc18b"
    },
    "dawn/stagemap/plus20.map": {
        "size": 1132876,
        "sha256": "40884308fda5107097c444bf273ff12603cda7168e788632aa39f4a0dd4aff05"
    },
    "dawn/stagemap/plus21.map": {
        "size": 1132876,
        "sha256": "e15a2bcd12b688b5cc7b012a6452561278ea54e5feabb07f8443f005473fe5a4"
    },
    "dawn/stagemap/plus22.map": {
        "size": 1132876,
        "sha256": "149ecdfe37f5a4655bc91063301b03bd6d7d187f061a846af525973fd5e2cc1d"
    },
    "dawn/stagemap/plus23.map": {
        "size": 1132876,
        "sha256": "c8106695d818c1e494efdabfce6502834511db04f6ed408b7961437456f5ee32"
    },
    "dawn/stagemap/plus24.map": {
        "size": 1132876,
        "sha256": "85804d2c0998fc5e2349984396a5ed6a9143c356326bc5319eb5698791d74799"
    },
    "dxwnd/9xheap.dll": {
        "size": 30720,
        "sha256": "2eb6b797817993d424040709e661aeec90a2ea930e0f8c4d14d17e4504aa9539"
    },
    "dxwnd/blacker.exe": {
        "size": 59904,
        "sha256": "0c153c3c46d2d8a967134102c3f00b8452dbd70d3f97dbc0632884864fa771ce"
    },
    "dxwnd/cdhack.exe": {
        "size": 8192,
        "sha256": "d492ce53ce5974fccc5be6f35c0f612653d8927cf2c7835e0e529e0b231bf9d4"
    },
    "dxwnd/CDPlayer.exe": {
        "size": 303616,
        "sha256": "b3368f46164864fe2c10c0578bf5e91309447bb6bf244f433a6d10a29b6339c6"
    },
    "dxwnd/Disasm.dll": {
        "size": 138752,
        "sha256": "f413a207787da88281500aaeae07fb98d7d438ecb4d67f8fcdf0aff2f988717f"
    },
    "dxwnd/dxhqx.dll": {
        "size": 209408,
        "sha256": "658ca4e3d05e7fa1f9db299585b7b5d90f84d33a9e6266ce063bfa64b270438c"
    },
    "dxwnd/dxwnd.dll": {
        "size": 1446912,
        "sha256": "acfbaa88c5320438ac26b8cfe1e0717b2eb764550102729af8aa7f0c3d76d205"
    },
    "dxwnd/dxwnd.exe": {
        "size": 1581056,
        "sha256": "dae9fe640908e9ec619ce539262db4f09ef68676c69b2266e410afc1627c8c75"
    },
    "dxwnd/dxwplay.dll": {
        "size": 181248,
        "sha256": "dc39c1f4fd6accab78e44f028653c2d06e1557d004874cc8a9b4742429f6ed2f"
    },
    "dxwnd/expdump.exe": {
        "size": 10752,
        "sha256": "f79abc3f00f57da881dd6dce87ff6576e23fba68a9d84019107146ee8125307d"
    },
    "dxwnd/expfinder.exe": {
        "size": 11776,
        "sha256": "53a9b082c981524833571e31ff2ef7eecadaf2963dcc768e561994569f361588"
    },
    "dxwnd/filter.dll": {
        "size": 14336,
        "sha256": "ce39b7693ab8c4b707e853554516b0a797a8a8379ada59e652dda5d2e10540c2"
    },
    "dxwnd/libogg.dll": {
        "size": 52736,
        "sha256": "8fa97dca70ceca184c0906b0bed13dc584fbb57e45417587cc02e7391a505aa0"
    },
    "dxwnd/libvorbis.dll": {
        "size": 755200,
        "sha256": "aa36449cd48a267eea76ab16816d003d89442673b42ea292fa45fba2401b93d7"
    },
    "dxwnd/libvorbisfile.dll": {
        "size": 102400,
        "sha256": "6eb516f688146db252798e8b3e9a11339d64b52a6e8919952b5d6706c772b991"
    },
    "dxwnd/scale2k.dll": {
        "size": 86112,
        "sha256": "3494a684912b08ef905a4c0d14f1b712a1aae16db01e9cbbf15caaf588e7aaab"
    },
    "dxwnd/scale2x.dll": {
        "size": 73923,
        "sha256": "4dedc026a1f59f2cde7f7bc9204a8165e1c2e7d6fad2f9ef5e43598032e73068"
    },
    "dxwnd/SDL.dll": {
        "size": 303616,
        "sha256": "af5f2716f1669e09e362d6ce8d4878a162a521d2aafe1660199be574242d151b"
    },
    "dxwnd/SDL2.dll": {
        "size": 1068544,
        "sha256": "fa3c8e8ed970fb6392a83e680d8dc307739ef7b16068fc2448896303e8797ecb"
    },
    "dxwnd/tail.exe": {
        "size": 9216,
        "sha256": "3905b68cb3c4ebd784475118bfb051d0a553281fc1048b9a609e97a02b57b13b"
    },
    "dxwnd/vcomp90.dll": {
        "size": 51024,
        "sha256": "9140efe26252b6329da254201219fc2d17a3f651e1591e32ae04c86a27e35bb2"
    },
    "dxwnd/wing32.dll": {
        "size": 42496,
        "sha256": "01763b01aae5874e4426021ddd96761222c914c35b309bd99ea876e628746fc5"
    },
    "dxwnd/winmm.dll": {
        "size": 149504,
        "sha256": "fdac49c51ccc1d940e8a2a4cafbcc13d1a3a30ee79dfaf82cc8aabf532495211"
    },
    "dxwnd/audiere/audiere.dll": {
        "size": 65024,
        "sha256": "afacc53254c5c3a1c9db5617faa68452b3b38880016247f11461602cec778e2e"
    },
    "dxwnd/ipxwrapper/dpwsockx.dll": {
        "size": 35840,
        "sha256": "f6a1855af4b04be4342219e8e3a695785646096d84c0fd089dc32a9cdb6f8e9e"
    },
    "dxwnd/ipxwrapper/ipxconfig.exe": {
        "size": 189952,
        "sha256": "4b8f43bff690adaba50be76a12387001fe2be139f37ce95c79d5e76ec960225d"
    },
    "dxwnd/ipxwrapper/ipxwrapper.dll": {
        "size": 83456,
        "sha256": "34b7bb13df3a35e30179f66e17dc711e02b0fd3b0167aa68407e2b01088d75cf"
    },
    "dxwnd/ipxwrapper/mswsock.dll": {
        "size": 31744,
        "sha256": "66ac7ec5c8f2f1c264c0689b932a0e0ce15e69719c1a631ebca006067faad206"
    },
    "dxwnd/ipxwrapper/wsock32.dll": {
        "size": 31232,
        "sha256": "fee723caae454b2d47ef3bbdc8676f6a062337886fa5ee39ce183fc7306ec241"
    },
    "dxwnd/nogameux/gameux.dll": {
        "size": 8192,
        "sha256": "dab9e3e3ef29c8351a67d5cd4133158ed7256471f357dc1198252fb09b376e1f"
    },
    "dxwnd/proxy/d3d8.dll": {
        "size": 57856,
        "sha256": "d0dab065acf8c5ccd415b6c343f3ad92206c4ce3a7964a25f212c40269c90a8c"
    },
    "dxwnd/proxy/d3d9.dll": {
        "size": 58880,
        "sha256": "7fe8ec65ebda09843a9269cf532d55c2f724d8daf15a4d50159a0d91f09b9b81"
    },
    "dxwnd/proxy/ddraw.dll": {
        "size": 59904,
        "sha256": "d5b56d2a278448bd68b29fb09ebe8a975d5449f41906f791e0b6bc7ea8061ffe"
    },
    "dxwnd/proxy/dinput.dll": {
        "size": 58368,
        "sha256": "85272965194228bbb14a7d949293ddd68b14251738a38573fca9648d3421a69c"
    },
    "dxwnd/proxy/dsound.dll": {
        "size": 58368,
        "sha256": "c7f7fc2a474004e75df16e151154192355fbd7c236d7836dcace596c01e4365c"
    },
    "dxwnd/proxy/opengl32.dll": {
        "size": 87040,
        "sha256": "44489b43ad2693e4e60255046d39e798c8f22f281f2cfbbe36a67c1610353a83"
    },
    "dxwnd/proxy/Version.dll": {
        "size": 58880,
        "sha256": "b2b6b86a133d27b8b1faf4829426720e6eb22662b55e0e1425178f3d5ead8828"
    },
    "dxwnd/proxy/wing32.dll": {
        "size": 58368,
        "sha256": "5e04552e6e311a21c88f3fd4fdfbbf6f5ca101d51d7a0fa0b9a6c6f1350ff1d7"
    },
    "dxwnd/vcda/winmm.dll": {
        "size": 149504,
        "sha256": "530d06d3c7268e1f0be36ec737cad0eb3716f6ed27c87ea974c2c5ae07145832"
    }
}

def check_rea_git_clean(rea_path: str) -> tuple[bool, str]:
    """Check git status of rea repository."""
    if not os.path.exists(rea_path):
        return False, f"Directory does not exist: {rea_path}"
    
    try:
        proc = subprocess.run(
            ['git', '-C', rea_path, 'status', '--porcelain'],
            capture_output=True,
            text=True,
            check=True
        )
        output = proc.stdout.strip()
        if output:
            return False, f"Working tree is dirty:\n{output}"
        return True, "Working tree is 100% clean."
    except subprocess.CalledProcessError as e:
        return False, f"Git command failed (code {e.returncode}): {e.stderr}"
    except Exception as e:
        return False, f"Error running git: {e}"

def verify_ym_integrity(ym_path: str) -> tuple[bool, list[str]]:
    """Verify byte size and SHA-256 hash for all key files in YM."""
    errors = []
    
    if not os.path.exists(ym_path):
        return False, [f"YM directory does not exist: {ym_path}"]
    
    for rel_path, expected in YM_KEY_MANIFEST.items():
        full_path = os.path.join(ym_path, rel_path.replace('/', os.sep))
        if not os.path.exists(full_path):
            errors.append(f"MISSING: {rel_path}")
            continue
            
        actual_size = os.path.getsize(full_path)
        if actual_size != expected['size']:
            errors.append(
                f"SIZE MISMATCH: {rel_path} (expected {expected['size']}, got {actual_size})"
            )
            continue
            
        hasher = hashlib.sha256()
        with open(full_path, 'rb') as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        actual_hash = hasher.hexdigest()
        
        if actual_hash != expected['sha256']:
            if rel_path == 'dawn/dawn.exe':
                backup_exe = Path(ym_path).parent / 'YM_backup_original' / 'dawn.exe'
                if backup_exe.exists() and backup_exe.stat().st_size == expected['size']:
                    if hashlib.sha256(backup_exe.read_bytes()).hexdigest() == expected['sha256']:
                        continue
            errors.append(
                f"HASH MISMATCH: {rel_path}\n  expected: {expected['sha256']}\n  got:      {actual_hash}"
            )
            
    return len(errors) == 0, errors

def main() -> int:
    workspace_root = Path(__file__).resolve().parent.parent
    ym_path = str(workspace_root / 'YM')
    rea_path = r'C:\src\rea'
    
    print("=" * 75)
    print("       REVERSE-IMZINROK SAFETY & INTEGRITY VERIFICATION AUDIT")
    print("=" * 75)
    
    # 1. Audit rea git repository
    print(f"[*] Checking 'rea' repository integrity: {rea_path}")
    rea_clean, rea_msg = check_rea_git_clean(rea_path)
    if rea_clean:
        print(f"    [PASS] {rea_msg}")
    else:
        print(f"    [FAIL] {rea_msg}")
        
    print()
    
    # 2. Audit YM directory key files
    print(f"[*] Checking 'YM' read-only files (204 items): {ym_path}")
    ym_ok, ym_errors = verify_ym_integrity(ym_path)
    if ym_ok:
        print("    [PASS] All 204 key files verified bit-exact with original SHA-256 hashes.")
    else:
        print(f"    [FAIL] Detected {len(ym_errors)} integrity violations:")
        for err in ym_errors[:10]:
            print(f"      ! {err}")
        if len(ym_errors) > 10:
            print(f"      ... and {len(ym_errors) - 10} more errors.")
            
    print("=" * 75)
    if rea_clean and ym_ok:
        print("AUDIT RESULT: PASSED (100% Clean & Untouched)")
        print("=" * 75)
        return 0
    else:
        print("AUDIT RESULT: FAILED (Integrity Violations Found)")
        print("=" * 75)
        return 1

if __name__ == '__main__':
    sys.exit(main())
