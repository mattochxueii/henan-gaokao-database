"""Original scripts. The speaker labels and production notes are not student text."""

texts = [
"""W: Are those the posters for the match? I can put one up in the dining hall on my way to lunch.
M: Thanks, but look at the date. These are the old ones. The new design is on my screen, waiting for someone to fill the printer with paper.
W: I'll get some from the office.""",
"""M: I was going to catch the ten-fifteen train. That would give us ages before the concert at twelve.
W: It doesn't run on Sundays, remember? The next one's at eleven. If you meet me on the platform at a quarter to eleven, we'll have time to get seats.
M: See you there, then.""",
"""W: I know you wanted to borrow my blue jacket for your picture. I'm wearing it to work, I'm afraid.
M: Never mind. They only need a picture of my face for the card. I'll go as I am.""",
"""M: That last bend on the river looked black in your painting. Did you run out of blue?
W: I had plenty. I wanted you to look first at the bright little boat. If I'd made the water bright too, you'd hardly have noticed it.""",
"""W: Are you coming down for a slice of cake? It's Ben's last day.
M: Save me one, will you? I've got someone on the other line. She's been waiting for me to check her booking.
W: I'll tell Ben you'll be along in a minute.""",
"""M: Did you find the missing page from the school magazine, Nia?
W: It was there the whole time, Sam. Two pages had stuck together. But I'm glad I checked. The photo under the heading "Spring Show" is of the winter concert.
M: Can't we change the heading?
W: Look at the article underneath. It's about the spring dancers. We need a different picture.
M: I took one from the front row. Shall I send it?
W: Please, in its original size. I can cut the edges off here. And don't worry about writing a line for it; the dancers have already sent their names.""",
"""W: Is the round table by the window still for sale?
M: It is. I put it online yesterday. It's forty pounds, or fifty if I bring it round in my van.
W: My brother has a car. The problem is getting it through the narrow door at my flat. Can the legs come off?
M: Yes. I took them off when I moved here. There's a little bag of spare screws underneath.
W: Lovely. My brother finishes work at six, so we could come about seven.
M: Fine. It's a turning off King Street. People usually stop at the green door because my address is number nine, but that's the front of the house. Drive round to the blue gate. I'll bring it out there.
W: Good. I'll bring the forty in cash.""",
"""M: How was your first morning at the radio station, Grace? Were you on air?
W: Only my left shoe! They were recording a play, and they needed someone walking upstairs. I crossed the studio in my trainers. It sounded as if I was walking on a carpet.
M: Wasn't the scene set in a hotel?
W: Yes, but the stairs were supposed to be bare wood. A man gave me a pair of hard shoes and a short board to walk on. The sound was right, only I was walking too fast.
M: How did you know?
W: The actress was out of breath when she reached the top in the story. At my speed she'd have been there before she even started speaking. So I watched her hand. She raised a finger each time she wanted another step.
M: Will you get to speak next time?
W: They've asked me back to make rain. After this morning I'm rather curious to find out what they use.""",
"""W: Before we open the little bookstall, Mr Reed, can I check how the prices work? The sign says two pounds for paperbacks, three for hardbacks.
M: That's for this first hour. After eleven, everything on the left table is a pound. The right table stays as it is. Most of the children's books are there.
W: And those books under your chair?
M: A teacher asked for books about the sea. I chose six for her school. She hasn't seen them yet. Would you keep them there until she comes?
W: Certainly. Do I give people one of these cards when they buy something?
M: Only if they ask about giving us books. The address of our store is printed on the back. For today's sale, people can just choose their books and pay you.
W: What if somebody wants to pay with a card?
M: Send them to me at the right table. Here's some change for cash sales.""",
"""W: If you're here for the first time, welcome to the North Street Swimming Club. I'm June and I look after the club records. Three years ago I found a tin full of little brass discs in the old office. At first I thought they were medals. Then I noticed the same numbers appeared over and over again, but never a swimmer's name. An older member showed me a picture of the changing room in the 1970s. You can just see a boy handing a disc to the woman behind the counter. She kept swimmers' clothes in numbered baskets. The discs were how people got their own clothes back.
We'd like to put that photograph in our entrance hall. The trouble is, the person who took it is still unknown. If you know who stood behind the camera, come and see me after the meeting. Several people have already told us the boy's name, so that part is settled. Next month we're having an open afternoon. You're welcome to bring old photographs then. We'll make copies on the spot and you can take the originals home the same day.""",
]

items = [
("What will the woman do next?", ["Put up a poster.", "Change a date.", "Fetch some paper."], "C", "她先提议贴海报，得知新版待打印后改为去办公室拿纸；没有要修改设计日期。"),
("When will the speakers meet?", ["At 10.45.", "At 11.00.", "At 12.00."], "A", "a quarter to eleven 是会合时刻；十一点是发车，十二点是音乐会。"),
("Why does the man no longer need the jacket?", ["He will take the picture at work.", "His clothing matters little for the picture.", "He can borrow another one for the picture."], "B", "办卡只需要脸部照片；work 是女士穿夹克的去处，没有另借的安排。"),
("Why did the woman paint the water dark?", ["To make the bend look deeper.", "To show the colour of the river.", "To draw attention to the boat."], "C", "暗河水衬托亮船，优先引导视线到船上。问句提到缺蓝色，女士明确说颜料充足。"),
("What is the man probably doing?", ["Serving a customer on the phone.", "Making a booking for himself.", "Arranging a party for Ben."], "A", "另一条线上有等他核查预订的女士；预订属于来电者，送别聚会已经开始。"),
("What is wrong with the magazine?", ["An article is missing.", "A photograph is out of place.", "A heading names the wrong season."], "B", "页纸只是粘住；标题与春季舞者文章吻合，冬季照片才是错配。"),
("What does Nia ask Sam to do?", ["List the dancers' names.", "Cut the edges off his photo.", "Send the full-size picture."], "C", "Nia 要原尺寸照片，裁边她来做，舞者已给出姓名。"),
("What is the woman's concern about taking the table home?", ["Getting it through her door.", "Finding a car for the journey.", "Putting the right address online."], "A", "她说明 narrow door 后询问可否拆腿；哥哥有车，网上售货及房屋地址属于卖家。"),
("How much will the woman pay the man?", ["Ten pounds.", "Forty pounds.", "Fifty pounds."], "B", "自行取货四十，五十含送货，差额十英镑。"),
("Where will the speakers meet?", ["By the green door.", "On King Street.", "At the blue gate."], "C", "取货从房屋后方蓝门走，绿门是正门；房屋在 King Street 的岔道。"),
("What was Grace helping to produce?", ["A radio play.", "A programme about a hotel.", "An interview with an actress."], "A", "录制的是广播剧，酒店是故事场景，女演员在剧中说台词。"),
("Why did Grace change her shoes?", ["Her own pair was uncomfortable.", "The first recording was too quiet to hear.", "The footsteps sounded wrong for the stairs."], "C", "运动鞋听起来像走在地毯上，与设定的裸木楼梯不符；声音听得见，问题是质感。"),
("How did Grace get the timing right?", ["By counting the lines in the script.", "By following the actress's signals.", "By matching the man's walking speed."], "B", "演员每希望出现一步就抬一下手指；男子提供鞋和木板，没有示范速度。"),
("What changes after eleven?", ["Books on one table get cheaper.", "Children's books move to the left.", "Hardbacks cost the same on both tables."], "A", "左桌降至一镑，右桌维持原价，童书多数在右桌。"),
("Why are six books under Mr Reed's chair?", ["They still need to be priced.", "They have been paid for by a school.", "They are being held for a teacher to look at."], "C", "受托挑海洋图书后留给老师查看；老师还没见到，没有付款信息。"),
("Who should receive one of the printed cards?", ["A buyer who wants to pay by card.", "Someone who has books to give away.", "A teacher who orders books for a class."], "B", "卡背是收书地址，给想捐书的人；银行卡支付找 Mr Reed。"),
("What made June doubt the discs were medals?", ["Their numbers were repeated.", "Their metal was very light.", "Their box had a club name on it."], "A", "反复出现相同号码且无泳者姓名使她怀疑奖牌解释；铜质和铁盒是外观背景。"),
("What did swimmers use the discs for?", ["Entering the pool.", "Recording a race time.", "Collecting their clothes."], "C", "照片与老会员的解释将筹码号码对应到衣篮，凭筹码取回衣物。"),
("What information does June want now?", ["When the club first opened.", "Who took the photograph.", "What the boy in the picture was called."], "B", "男孩的姓名已知，现在寻找按快门的人以便展示照片。"),
("What will happen to photographs brought to the open afternoon?", ["They will be returned after copying.", "They will be kept until the next meeting.", "They will be put straight on the hall wall."], "A", "现场复制，当天取回原件；计划在门厅展出的特指早先提到的更衣室照片。"),
]
