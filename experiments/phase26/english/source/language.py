gap = """Looking Again at a Familiar Walk
Ask me what I passed between my flat and the bus stop this morning and I can give you a shopping list: two streets, one garden, a corner shop. Ask me the shape of the shop window and I'm suddenly in trouble. [36] _____ Next time you take a familiar walk, try carrying a pencil and a small piece of paper.
Choose one spot where you can stand comfortably for a minute. Give your sketch a boundary before you put anything inside it. [37] _____ Everything outside that little square can wait for another day. Otherwise a five-minute walk can easily turn into a project you never start.
Now suppose you've chosen a doorway. We all carry a simple picture of a door in our heads, usually a tall, neat rectangle. [38] _____ Does its top actually run level with the bottom of the window beside it? Let what you see settle the question, even if the result on your page looks rather odd.
You can also write on your drawing. Perhaps the person who has just opened the door is already halfway down the street. [39] _____ A note such as "green sleeve, a bunch of keys" can bring the moment back later.
Keep the paper and stop at the same spot on another morning. This time, do a quick sketch before unfolding the first one. [40] _____ Is the doorway narrower today, or did the bicycle leaning beside it make you draw it differently?"""
gap_options = {
"A":"There is no need to chase them with your pencil.",
"B":"Set that ready-made picture aside and compare two edges.",
"C":"The shopkeeper may be able to tell you how old the door is.",
"D":"Recognising a place, it seems, is a good deal easier than seeing it.",
"E":"With the two drawings side by side, small differences begin to show.",
"F":"It might take in just what you can see between two posts of a fence.",
"G":"Give the completed sketch to someone who has never taken that walk.",
}
gap_keys = [
("D","开头说得出沿途物件却说不出橱窗形状，概括熟悉与看清的差别，引出带纸笔再走。"),
("F","It 回指刚划定的观察范围，栅栏两柱给出实际取景方法，后句 little square 承接。"),
("B","that ready-made picture 回指脑中的标准长方形，compare two edges 又引出门顶和窗底的比较。"),
("A","them 回指 person；路人已走远，无须赶着把人画完，下一句改用文字记衣袖和钥匙。"),
("E","先画第二幅才展开第一幅，两幅可以并排；接下来的宽窄比较为并排观察举例。"),
]

cloze = """On the first Saturday of the junior chess tournament, I ran the results desk. I had made a chart with a tidy square for every score. By lunchtime every square was filled except one. I went looking for the [41] _____ game.
Two boys were still at their board, although the hall was almost [42] _____. The other players had gone upstairs for lunch. As I drew closer, the smaller boy knocked his own king over. I reached for my pen. Then the other boy stood the king up and put two captured pieces [43] _____ where they had been. They started again.
"Which one of you won?" I asked. Both pointed at the taller boy. "About twenty minutes ago," he said. So why were they still [44] _____?
The smaller boy had been one move from a win himself, or so he [45] _____. He wanted to find out. His opponent had [46] _____ to put the pieces where they had been just before the mistake. But each remembered the position a little [47] _____. Now they were trying both versions.
I wrote down the score and told them I needed their table for the next round. The little boy began to [48] _____ the pieces. His opponent held out a hand to stop him. "Where can we finish this?" he asked me.
Beside my desk stood a small table. It was meant to [49] _____ the prizes. I moved the silver cups to the windowsill. The boys carried their board across the room, slowly enough to keep the pieces in [50] _____.
By afternoon, players who had finished their games were [51] _____ around the small table, waiting for a turn to try a move again. Nobody asked me to [52] _____ those games. When a parent asked who was [53] _____ at my new table, I couldn't tell her.
Next time I drew up the hall plan, I marked a space beside the desk before I even counted the competition boards. I left it [54] _____ on the results chart. A good game, I had discovered, doesn't always end when the score is [55] _____."""
cloze_items = [
(["opening","practice","missing","home"],"C","唯一空着的成绩格引出寻找未登记的那盘棋。opening 对应赛程，practice 是之后的复盘。"),
(["empty","ready","silent","dark"],"A","午间其他棋手已散，只剩这桌未报分；棋局安静是常态，although 强调人已散仍在场。"),
(["aside","together","away","back"],"D","两枚已被吃掉的棋子又回到各自原来的格子，put ... back where they had been 表示复原。aside 和 away 指收起，together 只指并置。"),
(["competing","playing","counting","arguing"],"B","胜负已明而仍在走棋，后文解释这是复盘。双方已一致指出赢家，并非比赛还在继续或争执胜负。"),
(["promised","required","believed","admitted"],"C","他觉得自己差一步可赢，于是想验证；这不是承诺、规则或认错。"),
(["offered","happened","forgotten","refused"],"A","对手帮助还原局面，并继续陪他尝试两种版本；主动相助呼应后文阻止收棋。"),
(["recently","publicly","clearly","differently"],"D","下一句说尝试 both versions，意味着记忆有分歧。"),
(["point at","pack up","hand out","count on"],"B","比赛桌要腾给下一轮，于是准备收起棋子，对手拦住他另找桌子。"),
(["hide","sort","hold","wrap"],"C","桌上本摆奖杯，移到窗台后原桌腾空，故 hold the prizes。"),
(["place","sight","balance","doubt"],"A","小心端着棋盘是为保住原来的棋子位置；in sight 不解释缓慢平稳搬动的目的。"),
(["turning","guessing","hurrying","gathering"],"D","已赛完的棋手围到小桌旁排队尝试，gathering around 与 waiting for a turn 衔接。"),
(["join","score","shorten","arrange"],"B","与记分员原本职责、家长随后询问领先者相照应，不需登记复盘的胜负。"),
(["teaching","missing","leading","serving"],"C","没有为复盘计分，故无法告诉家长谁领先；小桌旁活动本身显然可见。"),
(["off","up","open","marked"],"A","赛场布局专门留桌，成绩表却不列这张桌子；leave it off the chart 表示从表上略去。"),
(["compared","predicted","disputed","recorded"],"D","正式比分登记后，棋手仍可从同一局面学东西，与开头成绩格呼应。"),
]

grammar = """In the print room of a small museum, a wooden drawer stands open on the counter. Inside it are rows of tiny wooden blocks, each [56] _____ (carry) a single letter. The letters look strange until you see an impression on paper. A printer must arrange them back to front so that the words will appear the right way round.
Last winter, the museum [57] _____ (receive) the drawer from a family printing business when its owner retired. Among the blocks was [58] _____ unusually large question mark. A photograph tucked beneath the drawer showed it on a poster for a village play. The actor [59] _____ name appeared below the mark was the owner's grandfather.
Visitors can now make a card of their own. They choose three [60] _____ (word) and set them in a frame. Before [61] _____ (add) ink, they check the letters in a mirror. Even a short message takes time, and the guides wait [62] _____ (patient) while a visitor works. Many visitors take pride [63] _____ the little differences between their prints. The letters may be straight, but one may print a little [64] _____ (dark) than the rest. For many visitors, that small difference is precisely what makes the card worth [65] _____ (keep)."""
grammar_keys = [
("carrying","each carrying ... 构成独立主格结构，block 与 carry 是主动关系，无并列连词再接谓语。"),
("received","Last winter 给出已结束的过去时间，museum 作主语，received 为全句谓语。"),
("an","第一次引入单数可数名词 question mark；unusually 以元音音素开头，用 an。"),
("whose","关系从句缺少 name 的定语；姓名属于先行词 actor，故用 whose。"),
("words","three 限定可数名词复数，故 word 加 s。"),
("adding","before 在此接动词作介词宾语，其逻辑主语是 they，故填 adding。"),
("patiently","修饰动词 wait，patient 的副词形式为 patiently。"),
("in","take pride in sth. 是固定搭配，后接令人自豪的具体对象。"),
("darker","than the rest 形成比较，a little 修饰比较级 darker。"),
("keeping","worth 后用动名词，the card is worth keeping 表示卡片值得保留。"),
]

application = """假定你是李华。外教 Jo 邀请你为校英文广播节目 One Minute, One Object 介绍一件校园里的物品。请给她写一封邮件，内容包括：
（1）推荐一件物品，并说说它与校园生活的联系；
（2）说明你会怎样利用声音，让听众认出这件物品。
注意：写作词数应为 80 左右。请按如下格式作答。
Dear Jo,
Yours,
Li Hua"""
app_sample = """Dear Jo,
I'd love to bring the metal stamp from our school library to your programme. Everyone who borrows a book hears it, but few of us ever look at it. I'd open with the sound of a book sliding across the desk. Then I'd turn the little wheels on the stamp and press it twice on a piece of paper. Before giving the answer, I'd let listeners hear our librarian say, “See you in two weeks!” That should bring the desk to mind.
Yours,
Li Hua"""
app_rubric = [
(4,"物品与节目任务：能识别所荐校园物品2分，结合学生的使用经历或校园场景说明与校园生活的联系2分。"),
(4,"声音方案：描写可听到或可现场制作的声音2分，说明用何种顺序、提示或语境让听众辨认2分。其他可行构思同等计分。"),
(4,"语言：用词和语法准确、语意清楚给4分；少数错误不妨碍理解给3分；基本可辨给1—2分；无可理解英文给0分。"),
(3,"邮件与组织：回应 Jo 的邀请、语气得体1分，信息组织连贯1分，称呼与结尾适当1分。按实际表现相加，空白或全篇无关给0分。"),
]
continuation = """On the morning we were moving out of our flat, my little sister May went missing. I found her in the kitchen with her back against the pantry door. A pair of bare feet stuck out from under her yellow raincoat, although it was a perfectly dry day.
"What are you doing?" I asked.
"Being four," she said. Then she stood on tiptoe. "Now I'm nearly six."
I knew what she meant. For every birthday Dad had stood us against that white door and drawn a line above our heads. Beside each line he had written a name and a date. There was a shaky red one where May had tried to measure me herself. The highest blue line was mine, made only last week. With the coats and pictures gone, that door looked more like us than anything else in the flat.
In the sitting room, Dad was folding the last empty box. Our new flat was only three streets away, but he had been carrying boxes up and down stairs since breakfast. When May asked him to take the door, he put the box down. "The next family will need somewhere to keep their food too," he said. "I'll give you five minutes before we lock up."
I took a picture of the marks with my phone. May looked at the screen, set the phone against the wall and tried to stand beside her red line. In the picture the whole door was shorter than her hand. She handed it back without a word.
Outside, the van driver sounded his horn. Dad went down to tell him we were nearly ready. Looking around the bare room, I noticed a roll of brown packing paper behind the bin. The white tape we'd used to close the boxes was still round my wrist."""
cont_prompt = """阅读上面材料，根据其内容和下列两段开头语续写两段，使之构成一篇完整的短文。续写词数应为 150 左右。请保留两段开头语。
I picked up the roll and called May over.
That evening, Dad found us in the kitchen of our new flat."""
cont_sample = """I picked up the roll and called May over. “Stand on this end.” I ran the paper up the door beside the marks and held it with tape. May knelt down with a pencil. I read out the names and dates, and she copied the lines onto the paper at exactly the same heights. At my newest line she had to hand the pencil up to me. We rolled the strip carefully, with “FLOOR” written at the bottom, and hurried downstairs.
That evening, Dad found us in the kitchen of our new flat. We'd unrolled the strip against the wall. May had her heels on the word “FLOOR” and was stretching toward six again. Dad sat down on a box to look. “Somebody's missing,” he said. He stood with his back to the paper and bent his knees until I could reach above his head. May laughed. “Stand straight, Dad. We've got chairs now!”"""
cont_rubric = [
(6,"第一段推进：利用纸卷或其他合乎情境的办法回应搬走后保留身高记忆的难题3分，写出兄妹合作或 May 的反应2分，能在短时间内完成或合理带往新家1分。"),
(6,"第二段收束：承接新家厨房和父亲到来2分，写出保留的记忆在新家起到的具体作用2分，以人物动作、话语或新标记呈现家庭关系2分。"),
(5,"衔接与视角：两段首句自然接入各1分，人称与时间线一致1分，前文细节如门、刻度、照片或搬家约束得到有意义的回扣2分。"),
(5,"语言：叙事清楚流畅、用词准确、句式自然给5分；少量瑕疵给3—4分；错误较多但情节部分可辨给1—2分；不能传意给0分。"),
(3,"组织：段内推进有序1分，两段过渡可信1分，结尾与前情形成完整情节1分。合理替代情节同等给分；空白、全篇抄题或全篇无关给0分。"),
]
