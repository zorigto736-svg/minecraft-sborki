package zorya.honestping.mixin;

import net.minecraft.client.multiplayer.ClientPacketListener;
import net.minecraft.network.protocol.ping.ServerboundPingRequestPacket;
import net.minecraft.util.Util;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import zorya.honestping.HonestPing;

/** Раз в секунду (20 тиков) — запрос пинга; сервер отвечает на него сразу. */
@Mixin(ClientPacketListener.class)
public abstract class ClientPacketListenerMixin {
    @Unique
    private int honestping$ticks;

    @Inject(method = "tick", at = @At("TAIL"))
    private void honestping$ping(CallbackInfo ci) {
        HonestPing.connectionTick(this);
        if (honestping$ticks++ % 20 == 0) {
            ((ClientPacketListener) (Object) this).send(new ServerboundPingRequestPacket(Util.getMillis()));
        }
    }
}
