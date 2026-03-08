"""
Modelfile configuration parser for online LLM APIs.
Extracts system prompt and parameters from Ollama modelfile format.
"""

def parse_modelfile(modelfile_path: str) -> dict:
    """
    Parse an Ollama modelfile and extract configuration.

    Args:
        modelfile_path: Path to the modelfile

    Returns:
        dict with keys:
            - system_prompt: str - The system prompt text
            - base_model: str - The base model name (from FROM line)
            - temperature: float - Temperature parameter
            - top_p: float - Top-p parameter
            - repeat_penalty: float - Repeat penalty parameter
    """
    config = {
        'system_prompt': '',
        'base_model': '',
        'temperature': 0.8,  # defaults
        'top_p': 0.95,
        'repeat_penalty': 1.2,
    }

    with open(modelfile_path, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    in_system_block = False
    system_lines = []

    for line in lines:
        stripped = line.strip()

        # Parse FROM line for base model
        if stripped.startswith('FROM '):
            config['base_model'] = stripped[5:].strip()

        # Parse SYSTEM block
        elif stripped.startswith('SYSTEM """'):
            in_system_block = True
            continue
        elif in_system_block:
            if stripped.endswith('"""'):
                # End of system block
                in_system_block = False
                continue
            system_lines.append(line)

        # Parse PARAMETER lines
        elif stripped.startswith('PARAMETER '):
            parts = stripped[10:].strip().split()
            if len(parts) == 2:
                param_name, param_value = parts
                if param_name == 'temperature':
                    config['temperature'] = float(param_value)
                elif param_name == 'top_p':
                    config['top_p'] = float(param_value)
                elif param_name == 'repeat_penalty':
                    config['repeat_penalty'] = float(param_value)

    # Join system prompt lines
    config['system_prompt'] = '\n'.join(system_lines).strip()

    return config


def get_aoba_config(modelfile_path: str = 'Aoba.modelfile') -> dict:
    """
    Convenience function to get Aoba configuration.

    Args:
        modelfile_path: Path to Aoba.modelfile (default: 'Aoba.modelfile')

    Returns:
        Configuration dict ready for use with online LLM APIs
    """
    return parse_modelfile(modelfile_path)


if __name__ == '__main__':
    # Test the parser
    config = get_aoba_config('Aoba.modelfile')
    print("=== Parsed Modelfile Configuration ===")
    print(f"Base Model: {config['base_model']}")
    print(f"Temperature: {config['temperature']}")
    print(f"Top-p: {config['top_p']}")
    print(f"Repeat Penalty: {config['repeat_penalty']}")
    print(f"\nSystem Prompt:\n{config['system_prompt']}")
