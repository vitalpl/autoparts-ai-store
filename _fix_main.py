with open('main.py', encoding='utf-8') as f:
    lines = f.readlines()
print('Before:', len(lines))
with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines[:332])
with open('main.py', encoding='utf-8') as f:
    print('After:', len(f.readlines()))
