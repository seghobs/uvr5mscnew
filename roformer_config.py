"""Translate equivalent publisher metadata for the installed Roformer runner."""
from copy import deepcopy


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
