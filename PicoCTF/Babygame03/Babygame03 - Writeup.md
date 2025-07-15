The binary is x86 32 bit that needs ld so from a linux 32bit so I've decided to start a 32bit linux docker


<img width="1052" height="782" alt="first_game_output" src="https://github.com/user-attachments/assets/d3a54b12-6806-45c8-a62f-639176581462" />



```bash
mkdir docker_debug && cd ./docker_debug
mkdir bins
cp ../game ./bins/game
docker build i386-debug .

docker run -it \
  --cap-add=SYS_PTRACE \
  --security-opt seccomp=unconfined \
  -v  "$(pwd)/bins":/home/debugger/bins i386-debug

# To attach
docker container ps
# Use the id from the ps for {id}
docker exec -it {id} /bin/bash

```


`move_player` is returning back to main to `0x804992c`
the return address of `move_player` should be at -0xad0 from the stack frame of `main`
so `0xae0 - 0xaa1 = 0x3f` distance from the start of the map array at the stack. (we can go back to index `(-1 * 90) + 4`  easily which is `-0x56` ) which leaves us with 0x17 steps forward... (using only the x_pos)

I can only change one byte at a time and that byte would return to its original if I'll try to perform another lX command and then move the player.... so we can change the 0x2c byte in `0x8049973` to be `0x8049986` which is this code section (after the counter increment)
<img width="736" height="137" alt="Pasted image 20250709000631" src="https://github.com/user-attachments/assets/fd961693-b4c2-486a-af66-d23db45d86f0" />


REMEMBER: I first have to move with the x_pos to whatever x pos I want before I underflow the y_pos because I don't want to ruin that stack area with 0x2e's...

#### Final flow
- We'll need to perform 4 times the ret addr override of `move_player` to `0x8049986` so we'll have the level num = 5 and the counter = 4 which should lead us to after the last increment to this code section
  <img width="834" height="76" alt="Pasted image 20250709005355" src="https://github.com/user-attachments/assets/4943c7ee-4fb2-4851-afa0-74442968ba52" />
  And it should break which will lead to the `win` function!



WIN!!!!!!
<img width="758" height="541" alt="Pasted image 20250710215042" src="https://github.com/user-attachments/assets/d8760a28-5299-49bb-a486-7cb7ab53dc56" />


