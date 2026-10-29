package zorya.honestping;

import java.util.Arrays;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import com.mojang.logging.LogUtils;
import net.minecraft.ChatFormatting;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.PlayerInfo;
import net.minecraft.network.chat.Component;
import org.slf4j.Logger;

/**
 * Честный пинг до сервера.
 *
 * Цифру в Tab считает сервер: замер раз в 15 с и сглаживание (старое×3 + новое)/4, начиная
 * с нуля, поэтому первые минуты после входа она сильно занижена. Здесь раз в секунду уходит
 * отдельный запрос (тот же, что у графика F3+3), сервер отвечает на него сразу, а показывается
 * середина последних пяти замеров — без сглаживания от нуля.
 */
public final class HonestPing {
    private static final int WINDOW = 5;
    // формат имени из Styled Player List на нашем сервере: «ник | 67 мс»
    private static final Pattern NAME_WITH_PING = Pattern.compile("^(.+?) \\| \\d+ мс$");

    private static final long[] samples = new long[WINDOW];
    private static int count;
    private static int next;
    private static volatile int current = -1;
    private static long total;
    private static Object connection;
    private static final Logger LOG = LogUtils.getLogger();

    private HonestPing() {
    }

    /** Новое соединение — старые замеры не к нему. */
    public static synchronized void connectionTick(Object listener) {
        if (listener != connection) {
            connection = listener;
            count = 0;
            next = 0;
            total = 0;
            current = -1;
        }
    }

    public static synchronized void record(long rtt) {
        if (rtt < 0 || rtt > 30_000) {
            return;
        }
        samples[next] = rtt;
        next = (next + 1) % WINDOW;
        count = Math.min(count + 1, WINDOW);
        long[] sorted = Arrays.copyOf(samples, count);
        Arrays.sort(sorted);
        current = (int) sorted[count / 2];
        if (total++ % 30 == 0) {  // раз в полминуты — в журнал игры, чтобы было с чем сверять
            LOG.info("[Честный пинг] {} мс (последний замер {} мс)", current, rtt);
        }
    }

    private static boolean isLocal(PlayerInfo info, Minecraft minecraft) {
        return current >= 0 && minecraft.player != null
                && minecraft.player.getUUID().equals(info.getProfile().id());
    }

    /** Задержка для полосок связи: своя — честная, чужая — как прислал сервер. */
    public static int latencyFor(PlayerInfo info, Minecraft minecraft) {
        return isLocal(info, minecraft) ? current : info.getLatency();
    }

    /** Своя строка Tab: число из имени «ник | N мс» заменяется честным; чужие не трогаются. */
    public static Component fixName(PlayerInfo info, Component original, Minecraft minecraft) {
        if (original == null || !isLocal(info, minecraft)) {
            return null;
        }
        Matcher m = NAME_WITH_PING.matcher(original.getString());
        if (!m.matches()) {
            return null;
        }
        int ping = current;
        ChatFormatting color = ping < 100 ? ChatFormatting.GREEN : ping < 200 ? ChatFormatting.GOLD : ChatFormatting.RED;
        return Component.literal(m.group(1))
                .append(Component.literal(" | ").withStyle(ChatFormatting.DARK_GRAY))
                .append(Component.literal(String.valueOf(ping)).withStyle(color))
                .append(Component.literal(" мс").withStyle(ChatFormatting.GRAY));
    }
}
