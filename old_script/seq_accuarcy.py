'''
script manuscript for calculate the sequencing accuracy
'''

import sys
import regex

num_of_insertion = 0
num_of_deletion = 0
mapped_len = 0


with open("cigar.txt",'r') as f:
    for cigar in f:
        cigar = cigar.strip()
        cigar_list = regex.findall("[0-9]*[A-Z]",cigar)
        for i in cigar_list:
            if 'I' in i:
                num_of_insertion += int(i[0:-1])
                mapped_len += int(i[0:-1])
            if 'D' in i:
                num_of_deletion += int(i[0:-1])
                mapped_len += int(i[0:-1])
            if 'M' in i:
                mapped_len += int(i[0:-1])


print(num_of_insertion, num_of_deletion, mapped_len)


#CIGAR = "67S9M1D54M1I23M1D12M3D12M2I8M1I10M1D10M1D3M2I57M1I1M1I5M1I4M1D27M3D20M2D39M1D1M1D11M2D30M1D7M1I19M3I25M2D12M1I11M1I11M2I30M1D22M1D3M2I4M1D7M1I3M1I9M1D7M2I12M1I19M2I54M3I2M1D4M2I14M1I12M4I3M1D1M4I31M1I18M1I42M1D4M1I2M2I4M1I3M2D1M1D31M1D9M1I8M1I49M1D4M2D7M1I34M2D21M1I6M2I34M1I10M2I15M1I22M4D16M3D9M1D7M2D7M1I31M1I10M1D4M1D2M2D12M1I59M1I8M2I20M1I35M1D2M1D12M4D9M1D7M2I40M2I3M2D10M1I15M1I6M2I1M3D22M1D17M2I10M1I6M2D7M1D1M1D7M1D48M2I5M1I10M3D19M1D3M1I83M1D5M2D10M74S"
#CIGAR_list = regex.findall("[0-9]*[A-Z]",CIGAR)

num_of_insertion = 0
num_of_deletion = 0
mapped_len = 0
for i in CIGAR_list:
    if 'I' in i:
        num_of_insertion += int(i[0:-1])
        mapped_len += int(i[0:-1])
    if 'D' in i:
        num_of_deletion += int(i[0:-1])
        mapped_len += int(i[0:-1])
    if 'M' in i:
        mapped_len += int(i[0:-1])
print(num_of_insertion, num_of_deletion, mapped_len)

@62fceccd-3c79-4eca-8f2b-c15487b517f1 runid=55b4e91bd72e2d6fa0b5f0f5137bcd3bc72aa067 sampleid=SHSY5Y_cDNA_bcode_test read=1671 ch=104 start_time=2018-01-17T02:34:32Z
CGGTGTACTTCGTTCAGTCAGGTGGTGTTGCAGCAGTTCCTTCGCCGTGACAAGCGTTGAAACCTTTGTCCCTCTTTCTGTTGGTGCTGATATTGCTGGGGGTGAAATATAGTGTGAGTACGAGATTGTTTACATCTGGTAATATTCTCAGGAATGAAGGTTGTAACACAAAAGATCCAAAACACGCTGTAAGGGACGCTTTGCTGCAAAGCGGAGAATGATTTGTTCCTGCGGCACCGAGCACTGTTTGAACTAGAAAAATGCTACAAGTGGGTCGTGAAAAACAGAAGACTGCGCATATTTGAGGGCGAAGAGACCAACGATATAGATCCGAACCGGATGACAACAGCTCAGCTAGAGACCTAAGAACGGTTAGTATAAGGCGGTATTTAAGACTAAGATGTGTGGCTTAACTTGAGCTGATGGTATTGGAACAAGTTGTACGCAGCTGTAAGCGAACCTTTATCTCTTATAATTCAGCTCCATCCACCTCAGAACAAGTCCCTGTGCGTGCACAGAGACGTACATCCTGATCAGATTCGGGGTTACACGAGATCTATCAAAACAGGCTCAGTCATCAAACACGCAATGACACGGTGCCTAAAAATTGGTCTAGATACGTAGGAAGAAGGAAGATAACTGTTCAGTACACGGCGTATAAGGTCGTCATTACCATTTCAGTGGACGACCATGGGACGAACAGAAAAACCATTATATTGCCCCCATTCCGATAGCAAGCCGTCTGGCAAGATACGGTGGGTCCACCCACATAAGTATCCCCGGGCTCCCTTTCCGAACTGCATGTGTAGTGAAGCTTAGTGTGCATTTTGTCTCTCGCCCGTTCTTTACTTAACCTTGACTTGCTAACGCCCAGCATGAAGATGTGCATGGCCGTAAGGGGTAGTTTATACGCGAGGTGTGCGGCTGGGCGTTTCTTCCCTACAAATACCTCCGTAATCAAAGCTCCAGATCAGTGCTGTTTTGTGATAACTAAAAAGGCAAGGTAAATGCAGGCCCGATTGCATCGAACTTGTCAGTGAACACTCGAACGCAGTTGAAACTTACTAAGCAAATCTCGAAGATGGAAATGCGTTAAGAAACCACAGATGGAAGAGATAGCACAAATAGTTACGGTAATGTTCGGATCATGCTGTTATTAGTTTTACGCCGGTCTGAGTCTTCCCGGCGTGCTCTCAAACAGATGCCGAAAAAAAAAAAATAAAAAAAAAAAAAAAGAAGATAGAGCGACAGACAAGTGAGAGGACGTTTCAACGC
+
-%'$$$$$&().31%'$)*$&$'$(,(%&')'$&&($'$*#%&')*1?@<<:<')++,1=?=889:<589:,/,@?C:D??;>9;4/32+(''+16<35>A=54CA>=.66C@>323-?:,,++))()56;?A?;D@>@A@?AE@@@+=46447))%%%(.,&&&&'-1:;777<11EJMOB<?;<<61,//01+;>A@CEB*-,&%#%$'10565498=;E??/57=@E;115>:8<FE227=?<=<,46>:428:<BA8$$,0348:5=7<=;8/.-<<??-&&((/23<?<&%%68<?=9)&(,3$%-.%1913367577A<452.%%)--726<<><A?:+.*3/A?42,8200+9?:&88<@BA48>?D+>@?<=BA/9=@FDDB==GFBF?(<9=:::96621**&)#%%'#898=;99,**+-1213265722',1+,(5$222445756633555/-/0*5540,%')*./+3@5;478>@<?00;=314+00113%%$1,-+-&$$#$$.3:239/,)**09:/'7474902%%29<<:8/&%)+++8,+12124.&&&$''''17840')-,%%%3@?><B>=749<E@<-<0.$(&&':618132;;-%%,%,/*1+,0,.8;>@C789A:A?@9=<74(48766<.)()B505((5326=A@@CD:9*543/.+*)**,&&'/9367;5511088776777)..118?=D>@<=:+0&%&'#%')*9:7687?20/49=88%%(./0/5763,,,1940-/2:<2281,&%&%%,/&&/3'/$$2..+/-//+-+/833+++344%-00922157E+43142,/42886@4,)+)#$$'22/()+77@A>:;435/.,-,(31/:1:;54,,3/975474873$37547-0$&&&46912''%*())2/--143&&075=;;4?=5.%&&&')$$%34602-0442<8:6-54%599/&9,5A9>C<88=4758=,<859==830%&(&('&&')0,+'((+'''?::82;/,5,,87<94/0#&628/-7;69(('#$++8CCB@>4)*)-0456/=?@:75%*9?E@DAA>FIFD@<<JE;>69;B>;?>@@>;;-**5336*,&%%,./,''0,4,'((367;<50C<=C948;>@H@EE>@A:ACFC>8--/3,,38586<::45$)*')1451).22<6:3(3-A88A@9E6G?E=A==;:72AB?:;9:541/.001248;>9;>7;8:1&&&*%#%.('.1268+$(&119021.%

