package zorya.honestping.mixin;

import net.minecraft.client.multiplayer.PingDebugMonitor;
import net.minecraft.network.protocol.ping.ClientboundPongResponsePacket;
import net.minecraft.util.Util;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import zorya.honestping.HonestPing;

/** Ответ на запрос пинга несёт время отправки — разница с «сейчас» и есть пинг. */
@Mixin(PingDebugMonitor.class)
public abstract class PingDebugMonitorMixin {
    @Inject(method = "onPongReceived", at = @At("HEAD"))
    private void honestping$pong(ClientboundPongResponsePacket packet, CallbackInfo ci) {
        HonestPing.record(Util.getMillis() - packet.time());
    }
}
