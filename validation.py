import sys, h5py, getopt, timeit, os
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict
from math import sqrt
import scrappy


sys.path.append(os.path.dirname(os.path.realpath(__file__)))
import helper
from dtw_2 import dtw_local_alignment



def sequence_to_squiggle(seq):
    '''input:
        sequence <str>
        output:
        numpy array:
            [[mean, std, dwell]...]
    '''
    simulated_seq = scrappy.sequence_to_squiggle(seq,rescale =True).data(
                            as_numpy = True, sloika = False)
    return simulated_seq

def expect_squiggle_dict(seqs=None, read_from_fasta = None, read_from_model = None):
    '''
    read squiggle data from scrappie, ready for dtw
    '''
    expect_squiggle_dic = defaultdict(list)
    
    if not seqs and not read_from_fasta and not read_from_model:
        exit("No valid input detected when generating expect squiggle")
    
    if seqs:
        for seq in seqs:
            squiggle = sequence_to_squiggle(seq)
            for mean, std, dwell_time in squiggle:
                expect_squiggle_dic[seq] += [[mean, std]] *int(round(dwell_time))
        
    return expect_squiggle_dic


def main():

    def print_help():
        print("\n\nUsage: python {} [OPTIONS] <fast5 filename>".format(argv[0]))
        print("Options:\n\tIndexing:")
        print('\t\t-s INT\tstart point of the signal')
        print('\t\t-e INT\tend point of the signal')
        print('\t\t-o INT\toutput csv name')
        print('\t\t-p INT\tbase position to be fetched')
        print('\t\t-w INT\twindow size around the -p, default 20')
        print("\t\t-q STR\tqueried candidates, seperate by comma")
        

        return None
      

    argv = sys.argv
    if len(argv) < 3:
        print_help()
        exit()
    
    try: 
        opts, args = getopt.getopt(argv[1:],"hs:e:o:m:f:q:p:w:",
                    ["help=","start=","end=","output_figure=",
                    "model=","fasta=","sequence=", "position=", "window="])
    
    except getopt.GetoptError:
        print_help()
        exit()
    
    
    start_pos, end_pos,read_from_model,read_from_fasta,sequence \
        = None, None, None, None, None

    t_position = None
    window = 20
    output_file = "Untiled"
    
    
    for opt, arg in opts:
        if opt in ('-h', "--help"):
            print_help()
            exit()
        elif opt in ("-s", "--start"):
            start_pos = int(arg)
        elif opt in ("-e", "--end"):
            end_pos= int(arg)
        elif opt in ("-o", "--output_csv"):
            output_file = arg
        elif opt in ("-m", "--model"):
            read_from_model = arg
        elif opt in ("-f", "--fasta"):
            read_from_fasta = arg
        elif opt in ("-q", "--sequence"):
            sequence = arg.strip().split(',')
        elif opt in ("-p", "--position"):
            t_position = int(arg)
        elif opt in ("-w", "--window"):
            window = int(arg)
    
    fast5_filename = args[0]

    outf = open(output_file,'w')
    
    outf.write("read id")
    for i in range(len(sequence)):
        outf.write(",z_score{},log_likelihood{},manhattan{}".format(i+1,i+1,i+1))
    
    outf.write('\n'+ fast5_filename)




    # get signal
    if start_pos and end_pos:
        signal = helper.read_raw_signal(fast5_filename, start_pos, end_pos)
    elif t_position:
        signal = helper.get_junction_signal_by_pos(fast5_filename, 
                       t_position, window)
    
    if not signal:
        for i in range(len(sequence)):
            outf.write(",NA,NA,NA")
        print("read discarded")
        exit(0)




    # take reverse compliment seq if nesseccary
    strand = helper.get_mapped_info_from_fast5(fast5_filename)["strand"]
    if strand == "-":
        sequence = [helper.reverse_complement(s) for s in sequence]

    # Normalisation
    signal = helper.normalization(signal,"z_score") # "median_shift" or "z_score"

    model_dic = expect_squiggle_dict(sequence, read_from_fasta, read_from_model)

    
    dtw_long = signal


    #print(sequence, model_dic)
    
    
    

    for key in sequence:

        dtw_short = np.array(model_dic[key])
        dtw_short[:,0] = helper.normalization(dtw_short[:,0], "z_score")
        dtw_short[:,1] = dtw_short[:,1]/sqrt(np.std(dtw_short[:,0]))

        #print("dtw_short")
        dtw_short = np.array(dtw_short)
        #print("Input queried signal: " + '\t'.join([str(i) for i in dtw_long]))

        #print("\n\n\nInput model: " + '\t'.join([str(i) for i in dtw_short]))

        #print("\n\n\nRunning DTW...")

        timer_start = timeit.default_timer()
        #dtw_long = np.repeat(dtw_long,3)
        #dtw_long = dtw_long[abs(dtw_long)-3 < 0]
        
        path1 , score1 = dtw_local_alignment(dtw_long, dtw_short, dist_type = "z_score")
        path2 , score2 = dtw_local_alignment(dtw_long, dtw_short, dist_type = "log_likelihood")   
        path3 , score3 = dtw_local_alignment(dtw_long, dtw_short, dist_type = 'manhattan')
        
        outf.write(',{},{},{}'.format(score1/len(path1),score2/len(path2),score3/len(path3)))
        
        timer_stop = timeit.default_timer()

        runtime = timer_stop - timer_start

        if False:
            #print("\n\nDTW finished, runtime: {} sec".format(timer_stop - timer_start))
            plt.figure(figsize=(10,7))
            plt.plot(dtw_long)
            
            for score, path in (score1, path1), (score2, path2),(score3, path3):
                path = np.array(path[::-1])
                #print("\n\n\nBest path start and end:\n{} {}".format(np.array(path)[0,1],np.array(path)[-1,1]))
                #print("\n\n\nBest path length:\n{}".format(len(np.array(path))))
                
                plt.plot(np.array(path)[:,1]-1, dtw_short[[np.array(path)[:,0]-1]][:,0],'g')
                plt.plot(np.array(path)[:,1]-1, dtw_short[[np.array(path)[:,0]-1]][:,0]\
                                                + dtw_short[[np.array(path)[:,0]-1]][:,1],'g--')

                plt.plot(np.array(path)[:,1]-1, dtw_short[[np.array(path)[:,0]-1]][:,0]\
                                                - dtw_short[[np.array(path)[:,0]-1]][:,1],'g--')

            plt.title(figure_name+"_"+key+\
            "\nDist: {:.2f}, path length: {}, Adjusted dist: {:.2f}".format(score,\
                        len(np.array(path)),score/len(np.array(path))),fontsize=20)
        
            plt.savefig(fast5_filename+"_"+key+".png")
                



if __name__ == "__main__":
    main()
