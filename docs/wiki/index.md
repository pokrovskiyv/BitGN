# BitGN Knowledge Wiki

*Compiled: 2026-04-12T12:05:18Z*

## Current State

- **Score**: 69.2% (Qwen3.5-397B-A17B)
- **Best Ever**: 92.5%
- **Trend**: +5pp (0 > 37 > 58 > 64 > 69)
- **Tasks**: 2 STABLE / 125 FLAKY / 20 DEAD
- **Fixes Attempted**: 19

## Health

- [PASS] run_history: 161 runs, latest 2026-04-12
- [WARN] t005 (0% win rate) — no recent cycle
- [WARN] t014 (0% win rate) — no recent cycle
- [WARN] t016 (0% win rate) — no recent cycle
- [WARN] t017 (0% win rate) — no recent cycle
- [WARN] t018 (0% win rate) — no recent cycle
- [WARN] t039 (0% win rate) — no recent cycle
- [WARN] t040 (0% win rate) — no recent cycle
- [WARN] t041 (0% win rate) — no recent cycle
- [WARN] t042 (0% win rate) — no recent cycle
- [WARN] t043 (0% win rate) — no recent cycle
- [WARN] t047 (0% win rate) — no recent cycle
- [WARN] t048 (0% win rate) — no recent cycle
- [WARN] t064 (0% win rate) — no recent cycle
- [WARN] t066 (0% win rate) — no recent cycle
- [WARN] t067 (0% win rate) — no recent cycle
- [WARN] t068 (0% win rate) — no recent cycle
- [WARN] t089 (0% win rate) — no recent cycle
- [WARN] t091 (0% win rate) — no recent cycle
- [WARN] t092 (0% win rate) — no recent cycle
- [WARN] t093 (0% win rate) — no recent cycle
- [INFO] 5 BYPASSES findings across redteam reports
- [WARN] sota-analysis.md not updated in 13 days
- [PASS] Tasks: 2 STABLE, 125 FLAKY, 20 DEAD
- [INFO] FLAKY: t000, t001, t01, t002, t02, t003, t03, t004, t04, t05, t006, t06, t007, t07, t008, t08, t009, t09, t010, t10, t011, t11, t012, t12, t013, t13, t14, t015, t15, t16, t17, t18, t019, t19, t020, t20, t021, t21, t022, t22, t023, t23, t024, t24, t025, t25, t026, t26, t027, t27, t028, t28, t029, t29, t030, t30, t031, t31, t032, t32, t033, t33, t034, t34, t035, t35, t036, t36, t037, t37, t038, t38, t39, t40, t43, t044, t045, t046, t049, t050, t051, t052, t053, t054, t055, t056, t057, t058, t059, t060, t061, t062, t063, t065, t069, t070, t071, t072, t073, t074, t075, t076, t077, t078, t079, t080, t081, t082, t083, t084, t085, t086, t087, t088, t090, t094, t095, t096, t097, t098, t099, t100, t101, t102, t103
- [WARN] DEAD: t005, t014, t016, t017, t018, t039, t040, t041, t042, t043, t047, t048, t064, t066, t067, t068, t089, t091, t092, t093
- [PASS] Reports: 71 eval, 23 cycle, 28 redteam

## Task Summary

| Task | Win% | Stability | Last 5 |
|------|------|-----------|--------|
| [t000](tasks/t000.md) | 40% (2/5) | FLAKY | L L W W L |
| [t001](tasks/t001.md) | 40% (2/5) | FLAKY | L L W L W |
| [t01](tasks/t01.md) | 42% (35/84) | FLAKY | W W W W W |
| [t002](tasks/t002.md) | 60% (3/5) | FLAKY | L L W W W |
| [t02](tasks/t02.md) | 68% (57/84) | FLAKY | W W W W W |
| [t003](tasks/t003.md) | 40% (2/5) | FLAKY | L L W W L |
| [t03](tasks/t03.md) | 55% (46/84) | FLAKY | L W L W W |
| [t004](tasks/t004.md) | 60% (3/5) | FLAKY | L L W W W |
| [t04](tasks/t04.md) | 85% (71/84) | FLAKY | W W W W W |
| [t005](tasks/t005.md) | 0% (0/5) | DEAD | L L L L L |
| [t05](tasks/t05.md) | 83% (70/84) | FLAKY | L W W W W |
| [t006](tasks/t006.md) | 20% (1/5) | FLAKY | L L W L L |
| [t06](tasks/t06.md) | 80% (67/84) | FLAKY | L W W W W |
| [t007](tasks/t007.md) | 40% (2/5) | FLAKY | L L W L W |
| [t07](tasks/t07.md) | 45% (38/84) | FLAKY | W W W W L |
| [t008](tasks/t008.md) | 60% (3/5) | FLAKY | L L W W W |
| [t08](tasks/t08.md) | 62% (52/84) | FLAKY | W L W W W |
| [t009](tasks/t009.md) | 60% (3/5) | FLAKY | L L W W W |
| [t09](tasks/t09.md) | 52% (44/84) | FLAKY | W L W L L |
| [t010](tasks/t010.md) | 40% (2/5) | FLAKY | L L L W W |
| [t10](tasks/t10.md) | 71% (60/84) | FLAKY | W W W W W |
| [t011](tasks/t011.md) | 60% (3/5) | FLAKY | L L W W W |
| [t11](tasks/t11.md) | 76% (64/84) | FLAKY | W W W W W |
| [t012](tasks/t012.md) | 40% (2/5) | FLAKY | L L L W W |
| [t12](tasks/t12.md) | 46% (39/84) | FLAKY | W W W W L |
| [t013](tasks/t013.md) | 60% (3/5) | FLAKY | L L W W W |
| [t13](tasks/t13.md) | 63% (53/84) | FLAKY | W W W W L |
| [t014](tasks/t014.md) | 0% (0/5) | DEAD | L L L L L |
| [t14](tasks/t14.md) | 62% (52/84) | FLAKY | W W W W L |
| [t015](tasks/t015.md) | 40% (2/5) | FLAKY | L L W W L |
| [t15](tasks/t15.md) | 82% (69/84) | FLAKY | L W W W L |
| [t016](tasks/t016.md) | 0% (0/5) | DEAD | L L L L L |
| [t16](tasks/t16.md) | 58% (49/84) | FLAKY | W W W W W |
| [t017](tasks/t017.md) | 0% (0/5) | DEAD | L L L L L |
| [t17](tasks/t17.md) | 67% (56/84) | FLAKY | W W W W L |
| [t018](tasks/t018.md) | 0% (0/5) | DEAD | L L L L L |
| [t18](tasks/t18.md) | 70% (59/84) | FLAKY | W W W W L |
| [t019](tasks/t019.md) | 40% (2/5) | FLAKY | L L L W W |
| [t19](tasks/t19.md) | 65% (55/84) | FLAKY | W W W W W |
| [t020](tasks/t020.md) | 60% (3/5) | FLAKY | L L W W W |
| [t20](tasks/t20.md) | 46% (39/84) | FLAKY | W W W L L |
| [t021](tasks/t021.md) | 40% (2/5) | FLAKY | L L W W L |
| [t21](tasks/t21.md) | 50% (42/84) | FLAKY | W W W L L |
| [t022](tasks/t022.md) | 20% (1/5) | FLAKY | L L L L W |
| [t22](tasks/t22.md) | 71% (60/84) | FLAKY | W W W W L |
| [t023](tasks/t023.md) | 20% (1/5) | FLAKY | L L L L W |
| [t23](tasks/t23.md) | 11% (9/84) | FLAKY | W L L L L |
| [t024](tasks/t024.md) | 60% (3/5) | FLAKY | L L W W W |
| [t24](tasks/t24.md) | 8% (7/84) | FLAKY | L W W L L |
| [t025](tasks/t025.md) | 20% (1/5) | FLAKY | L L L L W |
| [t25](tasks/t25.md) | 49% (41/84) | FLAKY | W W W W L |
| [t026](tasks/t026.md) | 20% (1/5) | FLAKY | L L L L W |
| [t26](tasks/t26.md) | 74% (51/69) | FLAKY | W L W W L |
| [t027](tasks/t027.md) | 40% (2/5) | FLAKY | L L L W W |
| [t27](tasks/t27.md) | 67% (46/69) | FLAKY | W W W W L |
| [t028](tasks/t028.md) | 60% (3/5) | FLAKY | L L W W W |
| [t28](tasks/t28.md) | 61% (42/69) | FLAKY | W W W W L |
| [t029](tasks/t029.md) | 60% (3/5) | FLAKY | L L W W W |
| [t29](tasks/t29.md) | 38% (26/69) | FLAKY | L W W L L |
| [t030](tasks/t030.md) | 60% (3/5) | FLAKY | L L W W W |
| [t30](tasks/t30.md) | 13% (9/69) | FLAKY | W W W L L |
| [t031](tasks/t031.md) | 60% (3/5) | FLAKY | L L W W W |
| [t31](tasks/t31.md) | 86% (55/64) | FLAKY | W W W W L |
| [t032](tasks/t032.md) | 60% (3/5) | FLAKY | L L W W W |
| [t32](tasks/t32.md) | 72% (13/18) | FLAKY | W W W W L |
| [t033](tasks/t033.md) | 60% (3/5) | FLAKY | L L W W W |
| [t33](tasks/t33.md) | 75% (6/8) | FLAKY | W W W W W |
| [t034](tasks/t034.md) | 60% (3/5) | FLAKY | L L W W W |
| [t34](tasks/t34.md) | 50% (4/8) | FLAKY | L L W W L |
| [t035](tasks/t035.md) | 40% (2/5) | FLAKY | L L L W W |
| [t35](tasks/t35.md) | 88% (7/8) | FLAKY | W W W W L |
| [t036](tasks/t036.md) | 40% (2/5) | FLAKY | L L L W W |
| [t36](tasks/t36.md) | 62% (5/8) | FLAKY | W W W W L |
| [t037](tasks/t037.md) | 20% (1/5) | FLAKY | L L W L L |
| [t37](tasks/t37.md) | 50% (4/8) | FLAKY | L W W L L |
| [t038](tasks/t038.md) | 60% (3/5) | FLAKY | L L W W W |
| [t38](tasks/t38.md) | 86% (6/7) | FLAKY | W W W W L |
| [t039](tasks/t039.md) | 0% (0/5) | DEAD | L L L L L |
| [t39](tasks/t39.md) | 86% (6/7) | FLAKY | W W W L W |
| [t040](tasks/t040.md) | 0% (0/5) | DEAD | L L L L L |
| [t40](tasks/t40.md) | 29% (2/7) | FLAKY | L W L L L |
| [t041](tasks/t041.md) | 0% (0/5) | DEAD | L L L L L |
| [t41](tasks/t41.md) | 100% (2/2) | STABLE | W W |
| [t042](tasks/t042.md) | 0% (0/5) | DEAD | L L L L L |
| [t42](tasks/t42.md) | 100% (2/2) | STABLE | W W |
| [t043](tasks/t043.md) | 0% (0/5) | DEAD | L L L L L |
| [t43](tasks/t43.md) | 50% (1/2) | FLAKY | L W |
| [t044](tasks/t044.md) | 40% (2/5) | FLAKY | L L L W W |
| [t045](tasks/t045.md) | 60% (3/5) | FLAKY | L L W W W |
| [t046](tasks/t046.md) | 20% (1/5) | FLAKY | L L L L W |
| [t047](tasks/t047.md) | 0% (0/5) | DEAD | L L L L L |
| [t048](tasks/t048.md) | 0% (0/5) | DEAD | L L L L L |
| [t049](tasks/t049.md) | 40% (2/5) | FLAKY | L L W W L |
| [t050](tasks/t050.md) | 60% (3/5) | FLAKY | L L W W W |
| [t051](tasks/t051.md) | 60% (3/5) | FLAKY | L L W W W |
| [t052](tasks/t052.md) | 60% (3/5) | FLAKY | L L W W W |
| [t053](tasks/t053.md) | 60% (3/5) | FLAKY | L L W W W |
| [t054](tasks/t054.md) | 40% (2/5) | FLAKY | L L W L W |
| [t055](tasks/t055.md) | 20% (1/5) | FLAKY | L L W L L |
| [t056](tasks/t056.md) | 60% (3/5) | FLAKY | L L W W W |
| [t057](tasks/t057.md) | 60% (3/5) | FLAKY | L L W W W |
| [t058](tasks/t058.md) | 60% (3/5) | FLAKY | L L W W W |
| [t059](tasks/t059.md) | 60% (3/5) | FLAKY | L L W W W |
| [t060](tasks/t060.md) | 20% (1/5) | FLAKY | L L L W L |
| [t061](tasks/t061.md) | 60% (3/5) | FLAKY | L L W W W |
| [t062](tasks/t062.md) | 40% (2/5) | FLAKY | L L L W W |
| [t063](tasks/t063.md) | 60% (3/5) | FLAKY | L L W W W |
| [t064](tasks/t064.md) | 0% (0/5) | DEAD | L L L L L |
| [t065](tasks/t065.md) | 60% (3/5) | FLAKY | L L W W W |
| [t066](tasks/t066.md) | 0% (0/5) | DEAD | L L L L L |
| [t067](tasks/t067.md) | 0% (0/5) | DEAD | L L L L L |
| [t068](tasks/t068.md) | 0% (0/5) | DEAD | L L L L L |
| [t069](tasks/t069.md) | 60% (3/5) | FLAKY | L L W W W |
| [t070](tasks/t070.md) | 60% (3/5) | FLAKY | L L W W W |
| [t071](tasks/t071.md) | 20% (1/5) | FLAKY | L L L W L |
| [t072](tasks/t072.md) | 40% (2/5) | FLAKY | L L L W W |
| [t073](tasks/t073.md) | 20% (1/5) | FLAKY | L L L L W |
| [t074](tasks/t074.md) | 60% (3/5) | FLAKY | L L W W W |
| [t075](tasks/t075.md) | 40% (2/5) | FLAKY | L L L W W |
| [t076](tasks/t076.md) | 60% (3/5) | FLAKY | L L W W W |
| [t077](tasks/t077.md) | 60% (3/5) | FLAKY | L L W W W |
| [t078](tasks/t078.md) | 60% (3/5) | FLAKY | L L W W W |
| [t079](tasks/t079.md) | 60% (3/5) | FLAKY | L L W W W |
| [t080](tasks/t080.md) | 40% (2/5) | FLAKY | L L L W W |
| [t081](tasks/t081.md) | 20% (1/5) | FLAKY | L L L L W |
| [t082](tasks/t082.md) | 60% (3/5) | FLAKY | L L W W W |
| [t083](tasks/t083.md) | 60% (3/5) | FLAKY | L L W W W |
| [t084](tasks/t084.md) | 60% (3/5) | FLAKY | L L W W W |
| [t085](tasks/t085.md) | 40% (2/5) | FLAKY | L L W W L |
| [t086](tasks/t086.md) | 40% (2/5) | FLAKY | L L L W W |
| [t087](tasks/t087.md) | 40% (2/5) | FLAKY | L L L W W |
| [t088](tasks/t088.md) | 60% (3/5) | FLAKY | L L W W W |
| [t089](tasks/t089.md) | 0% (0/5) | DEAD | L L L L L |
| [t090](tasks/t090.md) | 40% (2/5) | FLAKY | L L W L W |
| [t091](tasks/t091.md) | 0% (0/5) | DEAD | L L L L L |
| [t092](tasks/t092.md) | 0% (0/5) | DEAD | L L L L L |
| [t093](tasks/t093.md) | 0% (0/5) | DEAD | L L L L L |
| [t094](tasks/t094.md) | 60% (3/5) | FLAKY | L L W W W |
| [t095](tasks/t095.md) | 60% (3/5) | FLAKY | L L W W W |
| [t096](tasks/t096.md) | 40% (2/5) | FLAKY | L L W L W |
| [t097](tasks/t097.md) | 20% (1/5) | FLAKY | L L L L W |
| [t098](tasks/t098.md) | 20% (1/5) | FLAKY | L L L L W |
| [t099](tasks/t099.md) | 60% (3/5) | FLAKY | L L W W W |
| [t100](tasks/t100.md) | 40% (2/5) | FLAKY | L L W W L |
| [t101](tasks/t101.md) | 60% (3/5) | FLAKY | L L W W W |
| [t102](tasks/t102.md) | 60% (3/5) | FLAKY | L L W W W |
| [t103](tasks/t103.md) | 60% (3/5) | FLAKY | L L W W W |

## Pages

- [Scoreboard](scoreboard.md)
- [Fix Registry](fix-registry.md)
- [Vulnerability Catalog](vulnerability-catalog.md)
- [Health Report](health.md)
