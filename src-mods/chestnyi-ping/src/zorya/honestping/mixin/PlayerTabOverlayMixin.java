package zorya.honestping.mixin;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.components.PlayerTabOverlay;
import net.minecraft.client.multiplayer.PlayerInfo;
import net.minecraft.network.chat.Component;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.Redirect;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;
import zorya.honestping.HonestPing;

/** В своей строке Tab — честный пинг: и число в имени, и полоски связи. */
@Mixin(PlayerTabOverlay.class)
public abstract class PlayerTabOverlayMixin {
    @Shadow
    @Final
    private Minecraft minecraft;

    @Redirect(method = "extractPingIcon",
            at = @At(value = "INVOKE", target = "Lnet/minecraft/client/multiplayer/PlayerInfo;getLatency()I"),
            require = 0)
    private int honestping$bars(PlayerInfo info) {
        return HonestPing.latencyFor(info, minecraft);
    }

    @Inject(method = "getNameForDisplay", at = @At("RETURN"), cancellable = true)
    private void honestping$name(PlayerInfo info, CallbackInfoReturnable<Component> cir) {
        Component fixed = HonestPing.fixName(info, cir.getReturnValue(), minecraft);
        if (fixed != null) {
            cir.setReturnValue(fixed);
        }
    }
}
