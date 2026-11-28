import org.yorugram.moderation.ChannelPolicy;

final class ChannelPolicyTest {
    public static void main(String[] args) {
        check(true, "УБИВАЙТЕ\u200b  ЛЮДЕЙ!", "");
        check(true, "Title", "Призываем к нападению на людей");
        check(true, "Публикуем реальные убийства людей", "");
        check(true, "Title", "Ｗｅ ｗｉｌｌ ａｔｔａｃｋ ｃｉｖｉｌｉａｎｓ");
        check(true, "Призываем к убийству 18+", "");
        check(false, "Хорроры 18+", "Вымышленные сюжеты и страшные аниме-комиксы");
        check(false, "Убийство в Восточном экспрессе", "Книжный клуб");
        check(false, "18+ для взрослых", "Комиксы и аниме");
        check(false, "Kill Everyone", "Horror: a fictional movie discussion");
        check(false, "Новости о реальных убийствах", "Разбор судебных решений");
        check(false, "Против насилия", "Как помочь пострадавшим");
        System.out.println("11 channel policy cases passed");
    }

    private static void check(boolean expected, String title, String description) {
        if (ChannelPolicy.blocksCreation(title, description) != expected) {
            throw new AssertionError(title);
        }
    }
}
