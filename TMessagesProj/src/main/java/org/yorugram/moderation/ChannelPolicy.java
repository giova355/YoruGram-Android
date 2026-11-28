package org.yorugram.moderation;

import java.text.Normalizer;
import java.util.Locale;
import java.util.regex.Pattern;

public final class ChannelPolicy {
    private static final Pattern FORMAT = Pattern.compile("\\p{Cf}+");
    private static final Pattern SEPARATORS = Pattern.compile("[^\\p{L}\\p{N}]+");
    private static final Pattern VIOLENCE = Pattern.compile(
            "(?:^| )(?:"
            + "(?:убивай|убивайте|убь[её]м|расстреливаем|расстреляем)"
            + " (?:реальных людей|людей|прохожих|детей|мирных жителей|гражданских)"
            + "|(?:призыв|призываем) к (?:убийству|убийствам|нападению на людей)"
            + "|(?:публикуем|смотрим|выкладываем) (?:реальные убийства|реальные расстрелы) людей"
            + "|(?:kill|murder|shoot) (?:all |the )?(?:real people|civilians|children|bystanders)"
            + "|(?:let s|we will|join us to) (?:kill|attack|shoot) (?:all |the )?(?:people|civilians|children|bystanders)"
            + "|(?:call|calling) for (?:murder|killing civilians|attacks on civilians)"
            + "|(?:sharing|posting) (?:real murders|real executions) of people"
            + ")(?: |$)"
    );

    private ChannelPolicy() {
    }

    public static boolean blocksCreation(CharSequence title, CharSequence description) {
        return matches(title) || matches(description);
    }

    private static boolean matches(CharSequence value) {
        String normalized = Normalizer.normalize(value, Normalizer.Form.NFKC).toLowerCase(Locale.ROOT);
        normalized = FORMAT.matcher(normalized).replaceAll("");
        return VIOLENCE.matcher(SEPARATORS.matcher(normalized).replaceAll(" ").trim()).find();
    }
}
