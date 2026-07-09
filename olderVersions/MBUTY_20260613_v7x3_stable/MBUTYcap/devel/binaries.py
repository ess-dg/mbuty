
buffer = int.to_bytes(0xff00ff00ff00ff00ff00ff00ff00ff003f00ff00, length=20, byteorder='little')

G0 = -1
   
# AA  =  int.from_bytes(buffer[16:17], byteorder='little')

# print(bin(AA))

# print(hex(AA))
       
G0GEO   = int.from_bytes(buffer[16:17], byteorder='little')

print(bin(G0GEO))

print(hex(G0GEO))
    
G0temp  = (G0GEO & 0xC0) >> 6    #extract only first two MSB and shift right by 6

print('----')
print(bin(G0temp))
print(hex(G0temp))

G1 = (G0temp & 0x1)          #bit 6 - if 0 either calib or normal mode, if 1 clustered mode 
G2 = (G0temp & 0x2) >> 1     #bit 7 - if 1 calib or 0 normal mode, if bit 6 is 0

print('----')
print(bin(G1))
print(bin(G2))
print(hex(G1))
print(hex(G2))

print('----')

if G1 == 1:
    print('clustered mode')
    G0 = 2
elif G1 == 0:
    if G2 == 1: 
        print('calibration mode')
        G0 = 1
    elif G2 == 0: 
        print('normal hit mode')
        G0 = 0
        
#  #  #  #  #  #  #  #  #  #  # 
        
temp = int.to_bytes(0xafa5, length=2, byteorder='little')

ADC0temp = int.from_bytes(temp, byteorder='little')

mult0    = (ADC0temp & 0xE000) >> 13

print(bin(mult0))
