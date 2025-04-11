from anthropic import Anthropic


def test_claude_chat(api_key: str) -> bool:
    """Test Claude chat completion with the provided API key."""
    try:
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-3.5-sonnet",
            max_tokens=1000,
            messages=[{"role": "user", "content": "Hello, how are you?"}]
        )
        print("\nClaude Response:", response.content[0].text)
        return True
    except Exception as e:
        print(f"\nClaude API Error: {str(e)}")
        return False


def main():
    while True:
        api_key = input("\nEnter your Anthropic API key (or 'q' to quit): ").strip()
        
        if api_key.lower() == 'q':
            print("Exiting program...")
            break
            
        if not api_key:
            print("Error: API key cannot be empty")
            continue
            
        test_claude_chat(api_key)


if __name__ == "__main__":
    main()

