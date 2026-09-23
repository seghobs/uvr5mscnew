"""Instance-local Roformer progress; no timer-based or global tqdm patches."""
import math


def attach_roformer_progress(instance, frames, callback):
    if not callback or not getattr(instance, 'is_roformer', False):
        return None
    rate = int(instance.model_data_cfgdict.audio.sample_rate)
    # The installed Roformer loop advances by overlap * sample_rate samples.
    step = int(instance.overlap * rate)
    if step <= 0 or frames <= 0:
        return None
    total = math.ceil(frames / step)
    completed = 0

    def after_forward(module, args, output):
        nonlocal completed
        completed = min(total, completed + 1)
        callback(.25 + .70 * completed / total,
                 f'Ses ayrıştırılıyor · {completed}/{total} parça')
        # Returning None leaves the network output untouched.

    return instance.model_run.register_forward_hook(after_forward)
