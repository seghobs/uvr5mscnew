"""Translate equivalent publisher metadata for the installed Roformer runner."""
from copy import deepcopy


def install_bs_mask_expansion_support():
    """Support published narrow single-head masks without changing stock defaults."""
    from audio_separator.separator.architectures import mdxc_separator
    from audio_separator.separator.uvr_lib_v5.roformer.bs_roformer import MaskEstimator
    from torch import nn
    original=mdxc_separator.BSRoformer
    if getattr(original,'_supports_mask_expansion',False):return
    def construct(*args,mlp_expansion_factor=4,**kwargs):
        if mlp_expansion_factor not in (2,4):raise ValueError('Unsupported mask expansion')
        model=original(*args,**kwargs)
        if mlp_expansion_factor!=4:
            inputs=model.mask_estimators[0].dim_inputs
            model.mask_estimators=nn.ModuleList([
                MaskEstimator(dim=kwargs['dim'],dim_inputs=inputs,
                              depth=kwargs.get('mask_estimator_depth',2),
                              mlp_expansion_factor=mlp_expansion_factor)
                for _ in range(kwargs.get('num_stems',1))])
        return model
    construct._supports_mask_expansion=True
    mdxc_separator.BSRoformer=construct


def compatible_recovery_config(published):
    config=deepcopy(published)
    factor=config['model'].pop('mlp_expansion_factor',4)
    if factor not in (2,4):raise ValueError('Unsupported recovery model architecture')
    config=compatible_single_target_config(config)
    config['model']['mlp_expansion_factor']=factor
    return config


def reuse_legacy_safetensors(root, destination):
    """Move the old flat Leap cache into its isolated cache without network access."""
    from pathlib import Path
    import os
    import shutil
    import uuid
    import yaml
    from safetensors import safe_open
    root, destination = Path(root), Path(destination)
    if all((destination/name).is_file() for name in ('model.safetensors', 'config.yaml')):
        return True
    source, config_path = root/'model.safetensors', root/'config.yaml'
    if not source.is_file() or not config_path.is_file():
        return False
    # A generic config.yaml may belong to another model. Never adopt it blindly.
    config = yaml.load(config_path.read_text(encoding='utf8'), Loader=yaml.FullLoader)
    bands = config.get('model', {}).get('freqs_per_bands', ())
    with safe_open(source, framework='pt') as weights:
        indices = {int(key.split('.')[2]) for key in weights.keys()
                   if key.startswith('band_split.to_features.')}
        if not bands or indices != set(range(len(bands))):
            return False
    destination.mkdir(parents=True, exist_ok=True)
    for original in (source, config_path):
        target = destination/original.name
        if target.exists():
            continue
        temporary = target.with_name(target.name+'.tmp-'+uuid.uuid4().hex)
        try:
            shutil.copyfile(original, temporary)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    return True


def compatible_single_target_config(published):
    config = deepcopy(published)
    model = config['model']
    for option, expected in [('mlp_expansion_factor', 4), ('use_torch_checkpoint', False), ('skip_connection', False)]:
        if model.get(option, expected) != expected:
            raise ValueError('Published model architecture is not compatible with this runtime')
        model.pop(option, None)
    config['audio']['hop_length'] = model['stft_hop_length']
    training = config['training']
    target = training.get('target_instrument')
    if model.get('num_stems', 1) == 1 and target:
        instruments = training['instruments']
        if target not in instruments:
            raise ValueError('Single-target model target is missing from instrument labels')
        # The runner assigns the single output to the first instrument label.
        training['instruments'] = [target] + [item for item in instruments if item != target]
    return config
