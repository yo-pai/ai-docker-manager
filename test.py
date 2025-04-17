import os
import re
from anthropic import Anthropic
from dotenv import load_dotenv


def generate_docker_compose(user_requirement):
    """
    Generate a docker-compose.yaml file based on user requirements.

    Args:
        user_requirement (str): User's request for Docker containers.

    Returns:
        str: Generated docker-compose YAML content.
    """
    # Load environment variables (for API key)
    load_dotenv()

    # Docker expert prompt
    docker_expert_prompt = """你是一个docker专家，擅长编写docker-compose的yaml文件，可以基于用户给的需求进行docker-compose.yaml格式的文件编写，编写的时候你需要遵守；
1. 根据用户想要部署的容器进行yaml格式的文件构建
2. 如果用户提供了版本和一些默认参数的话，构建yaml格式的时候你需要注意加入
3. 平台使用platform: linux/arm64/v8
4. 如果有一些软件需要依赖，请在用户给出需求后，加入到yaml配置文件，例如kafka需依赖zookepeer
5. 只需要给出yaml格式的文件，不要生成其他任何解释和文字

用户需求:
"""

    # Combine prompt and user requirement
    combined_content = f"{docker_expert_prompt}\n\n{user_requirement}"

    # Initialize Anthropic client with API key from environment variables
    client = Anthropic(
        base_url='https://api.openai-proxy.org/anthropic',
        api_key='sk-wVjmhVkRDWZw52GWj9Ot3opAnbepiGIOUqfPF45982usryd0',
    )

    # Make API request with combined content
    try:
        message = client.messages.create(
            max_tokens=4080,
            messages=[
                {
                    "role": "user",
                    "content": combined_content,
                }
            ],
            model="claude-3-7-sonnet-20250219"
        )

        # Extract response content
        response_content = message.content[0].text

        # Remove markdown code blocks (```yaml and ```) from the response
        # This ensures the saved file contains only valid YAML
        response_content = re.sub(r'^```yaml\s*', '', response_content, flags=re.MULTILINE)
        response_content = re.sub(r'^```\s*$', '', response_content, flags=re.MULTILINE)
        response_content = response_content.strip()

        return response_content

    except Exception as e:
        return f"Error generating Docker Compose configuration: {str(e)}"


# Example usage
if __name__ == "__main__":
    user_input = input("Enter your Docker container requirements: ")
    yaml_config = generate_docker_compose(user_input)
    print("\n--- Generated Docker Compose YAML ---\n")
    print(yaml_config)

    # Optionally save to file
    save_file = input("\nSave to docker-compose.yaml? (y/n): ")
    if save_file.lower() == 'y':
        with open("docker-compose.yaml", "w") as f:
            f.write(yaml_config)
        print("File saved as docker-compose.yaml")