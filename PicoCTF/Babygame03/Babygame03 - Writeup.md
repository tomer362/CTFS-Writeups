The binary is x86 32 bit that needs ld so from a linux 32bit so I've decided to start a 32bit linux docker

![TEST](https://private-user-images.githubusercontent.com/16362777/466610044-dc169a65-ca95-43dd-a123-2f25df4bc1e3.png?jwt=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3NTI1OTg2MTAsIm5iZiI6MTc1MjU5ODMxMCwicGF0aCI6Ii8xNjM2Mjc3Ny80NjY2MTAwNDQtZGMxNjlhNjUtY2E5NS00M2RkLWExMjMtMmYyNWRmNGJjMWUzLnBuZz9YLUFtei1BbGdvcml0aG09QVdTNC1ITUFDLVNIQTI1NiZYLUFtei1DcmVkZW50aWFsPUFLSUFWQ09EWUxTQTUzUFFLNFpBJTJGMjAyNTA3MTUlMkZ1cy1lYXN0LTElMkZzMyUyRmF3czRfcmVxdWVzdCZYLUFtei1EYXRlPTIwMjUwNzE1VDE2NTE1MFomWC1BbXotRXhwaXJlcz0zMDAmWC1BbXotU2lnbmF0dXJlPTg0MDNjZmMwNDc1NmJmNmQ5ODk1ODM0NTg1YzFmNDQxOWY0N2FkOWU4MzU5ZTNlYWI5YTcxZjdiODNiMjhkOGImWC1BbXotU2lnbmVkSGVhZGVycz1ob3N0In0.iruYTFdq4A6-HEZy6ICmnIWXdLjWVJ20V_y1YyMUCnQ)



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
![[Pasted image 20250709000631.png]]

REMEMBER: I first have to move with the x_pos to whatever x pos I want before I underflow the y_pos because I don't want to ruin that stack area with 0x2e's...

#### Final flow
- We'll need to perform 4 times the ret addr override of `move_player` to `0x8049986` so we'll have the level num = 5 and the counter = 4 which should lead us to after the last increment to this code section
  ![[Pasted image 20250709005355.png]]
  And it should break which will lead to the `win` function!



WIN!!!!!!

![[Pasted image 20250710215042.png]]