import matplotlib.pyplot as plt
import concurrent.futures
import time
import sys
import h5py
import getopt
import timeit
import os
import numpy as np
import re
import fcntl
import pysam
from tqdm import tqdm
from intervaltree import Interval
from intervaltree import IntervalTree
from pathlib import Path
from ont_fast5_api.fast5_interface import get_fast5_file   
from scipy.stats.mstats import theilslopes     

import helper
from junction_identification import find_candidate, canonical_site_finder, \
                                                    candidate_motif_generator
from dtw import dtw


# parse command line arg
def parse_arg():
    def print_help():
        print("\n\nUsage: python {} [OPTIONS]".format(argv[0]))
        print("Options:\n\tIndexing:")
        print('\t\t-i \t.bam/.sam file (required)')
        print('\t\t-f \tpath to fast5s (directory path) (required)')
        print('\t\t-r \tGenome reference file (required)')
        print("\t\t-o \toutput path, default: 'NanoSplicer_out'")
        print('\t\t-T \tNumber of events trimmed from scrappie model')
        print('\t\t-t \tNumber of samples trimmed from raw signal')
        print('\t\t-F \tFlanking sequence size in each side')
        print('\t\t-w \twindow size for searching the candidate')
        print('\t\t-G \trun junctions in csv file')
        return None

    argv = sys.argv
    if len(argv) <= 2:     
        print_help()       # print help doc when no command line args provided
        sys.exit(0)
    
    try: 
        opts, args = getopt.getopt(argv[1:],"hi:f:r:o:T:t:ab:F:w:G:",
                    ["help=","input_alignment=","input_fast5_dir=",
                    "genome_ref=","output_path=", "trim_model=",
                    "trim_signal=","dtw_adj","bandwidth=",
                    "flank_size=", "window=","group="])
    
    except getopt.GetoptError:
        print_help()
        sys.exit(0)

    # DEFAULT VALUE
    alignment_file, fast5_dir, genome_ref = None, None, None
    output_path = 'NanoSplicer_out'
    trim_signal = 6
    trim_model = 2
    dtw_adj = False
    bandwidth = 0.4
    flank_size = 20
    window = 10


    for opt, arg in opts:
        if opt in ('-h', "--help"):
            print_help()
            sys.exit(0)
        elif opt in ("-i", "--input_alignment"):
            alignment_file = arg
        elif opt in ("-f", "--input_fast5_dir"):
            fast5_dir = arg
        elif opt in ("-r", "--genome_ref"):
            genome_ref = arg
        elif opt in ("-o", "--output_path"):
            output_path = arg
        elif opt in ("-T", "--trim_model"):
           trim_model = int(arg)
        elif opt in ("-t", "--trim_signal"):
           trim_signal = int(arg)
        elif opt in ("-a", "--dtw_adj"):
           dtw_adj = True
        elif opt in ("-b", "--bandwidth"):
           bandwidth = float(arg)
        elif opt in ("-F", "--flank_size"):
           flank_size = int(arg)
        elif opt in ("-w", "--window"):
           flank_size = int(arg)
        elif opt in ("-G", "--group"):
            group_filename = arg


    # check input
    if not alignment_file or not fast5_dir or not genome_ref:
        print("Error:Missing input files.")
        sys.exit(1)

    # choose the version of dtw (sum: minimize the sum of cost for the path)
    def dtw_local_alignment(candidate_squiggle, junction_squiggle, 
                            bandwidth = bandwidth, dist_type = None):
        
        return dtw(candidate_squiggle=candidate_squiggle,
                   junction_squiggle=junction_squiggle, 
                   band_prop = bandwidth,
                   dist_type = dist_type).dtw_local_alignment()
    
    return fast5_dir, output_path, alignment_file, genome_ref, \
            bandwidth, trim_model, trim_signal, flank_size, \
            window, group_filename

def count_in_tmp(filename):
    '''
        count once in a certain tmp file
    '''
    f = open(filename, "r+")
    fcntl.flock(f,fcntl.LOCK_EX)
    count = f.read()
    count = int(count) + 1 if count else 1
    f.seek(0)
    f.write(str(count))
    f.truncate()
    f.close()

def get_gaps_in_read(AlignedSegment):
    blocks = AlignedSegment.get_blocks()
    gap = set([(blocks[i-1][1], blocks[i][0]) for i in range(len(blocks))])
    return gap
    

def read_cases_from_file(filename):
    ids = []
    minimap_site = []
    NanoSplicer_site = []
    with open(filename, 'r') as f:
        for line in f:
            rid, mst, mnd, nst, nnd = line.strip().split(',')
            mst, mnd, nst, nnd \
                = int(mst), int(mnd), int(nst), int(nnd)
            ids.append(rid)
            minimap_site.append(Interval(mst, mnd))
            NanoSplicer_site.append(Interval(nst, nnd))
    return ids, minimap_site, NanoSplicer_site


def run_multifast5(fast5_path, all_junctions, AlignmentFile, ref_FastaFile, 
                    window, chrID, flank_size, trim_model, trim_signal,
                    bandwidth, output_file, group_filename):
    
    # dtw version
    def dtw_local_alignment(candidate_squiggle, junction_squiggle, 
                            bandwidth = bandwidth, dist_type = None):
        return dtw(candidate_squiggle=candidate_squiggle,
                   junction_squiggle=junction_squiggle, 
                   band_prop = bandwidth,
                   dist_type = dist_type).dtw_local_alignment()
    
    print("reading junction list file...")
    ids, minimap_site, NanoSplicer_site = read_cases_from_file(group_filename)


    # prepare the inputs
    AlignmentFile = pysam.AlignmentFile(AlignmentFile)
    ref_FastaFile = pysam.FastaFile(ref_FastaFile)
    multi_fast5 = get_fast5_file(fast5_path, 'r')
    reads_in_file = set(multi_fast5.get_read_ids())

    # set tmp filename
    output_path = output_file.split("/")[0]
    os.system("mkdir -p {}/.tmp".format(output_path))
    ftombo_fail = "{}/.tmp/tombo_resquiggle_fail.tmp".format(output_path)
    fbad_junction_mapping = "{}/.tmp/bad_junction_mapping.tmp".format(output_path)
    fno_signal_found = "{}/.tmp/detect_signal_fail".format(output_path)
    #fpass_squiggle = "{}/.tmp/count_pass.tmp".format(output_path)
    # loop thought each junction
    for i in range(len(minimap_site)):
        if ids[i] not in  reads_in_file:
            continue
        
        # find 
        junction = minimap_site[i]
        overlap_read = AlignmentFile.fetch(chrID, junction.begin, junction.end)
        
        read = None
        for read1 in overlap_read:
            #print(read.qname, ids[i])
            if read1.qname == ids[i]:
                print("{} found".format(read1.qname))
                read = read1
        if not read:
            print("read not found")
            sys.exit()

        print("processing {}".format(read.qname))
        if read.qname != ids[i]:
            exit("weird")
            continue

        if (junction.begin, junction.end) not in get_gaps_in_read(read)\
            or read.qname not in reads_in_file:
            continue




        donor_lst, acceptor_lst = canonical_site_finder(junction, 
                                          ref_FastaFile, AlignmentFile, 
                                          window, chrID)
        
        candidates_pos, candidate_motif, motif_start, motif_end = \
                candidate_motif_generator(chrID, donor_lst, acceptor_lst, 
                                          flank_size, ref_FastaFile)
        
        index_m = candidates_pos.index((minimap_site[i].begin, minimap_site[i].end))
        index_n = candidates_pos.index((NanoSplicer_site[i].begin, NanoSplicer_site[i].end))
        
        print(index_m, index_n)
        
        #two candidates mode
        if False:
            '''
            two candidates mode
            '''
            candidate_motif = [candidate_motif[index_m], candidate_motif[index_n]]
        if not candidate_motif:# or len(candidate_motif) == 1:
            continue

        candidate_motif_rev = [helper.reverse_complement(seq) 
                                for seq in candidate_motif]

        # trim signal (use fewer base)
        motif_start += trim_signal
        motif_end -= trim_signal
        

        # check reverse
        if read.is_reverse:
            candidates_for_read = candidate_motif_rev
        else:
            candidates_for_read = candidate_motif
            
        # tombo resquiggle
        try:
            tombo_results, tombo_start_clip, tombo_end_clip = \
                tombo_squiggle_to_basecalls(multi_fast5, read)
        except:
            #print("tombo resquiggle failed!!")
            count_in_tmp(ftombo_fail)

        read_length = len(tombo_results.genome_seq) \
                                + tombo_start_clip + tombo_end_clip
        normalised_raw_signal = tombo_results.raw_signal/1.4826

        # genome pos to read pos mapping vector
        g_r_mapping = \
            genome_to_read_pos_conversion(read.cigarstring)

        # convert to read relative pos (forward direction)
        start_pos_rel_to_mapped_start = motif_start - read.reference_start
        end_pos_rel_to_mapped_start = motif_end - read.reference_start

        if  start_pos_rel_to_mapped_start >= 0 \
                    and start_pos_rel_to_mapped_start < len(g_r_mapping):
            motif_start_read = g_r_mapping[start_pos_rel_to_mapped_start]
                
            # discard junction squiggle with the queried motif start/end 
            # mapped to gaps
            if motif_start_read == -1:
                #print("Warning: Junction squiggle start index point to 
                #mapped intron, junction squiggle skipped.")
                count_in_tmp(fbad_junction_mapping)
                continue
            elif g_r_mapping[start_pos_rel_to_mapped_start] == \
                g_r_mapping[start_pos_rel_to_mapped_start - 1]:
                motif_start_read += 1 
        else:
            #print("candidate start pos out of bound.")
            count_in_tmp(fbad_junction_mapping)
            continue

        
        if end_pos_rel_to_mapped_start < len(g_r_mapping):
            motif_end_read = g_r_mapping[end_pos_rel_to_mapped_start - 1] + 1
            
            # discard junction squiggle with the queried motif start/end 
            # mapped to gaps
            if motif_end_read == -1 + 1:
                #print("Warning: Junction squiggle end index point to" 
                # "mapped intron, junction squiggle skipped.")
                count_in_tmp(fbad_junction_mapping)
                continue
        else:
            #print("candidate end pos out of bound.")
            count_in_tmp(fbad_junction_mapping)
            continue

        # get signal
        if not read.is_reverse:
            seg_start = max(motif_start_read - tombo_start_clip, 0)
            seg_end = motif_end_read - tombo_start_clip
        else:
            seg_start = \
                max(read_length - motif_end_read -1 - tombo_start_clip, 0)
            seg_end = read_length - motif_start_read - 1 - tombo_start_clip
        # take into account the end clip
        seg_end = min(seg_end, len(tombo_results.segs) - 1)
        
        signal = normalised_raw_signal[
            tombo_results.segs[seg_start]:tombo_results.segs[seg_end]]

        
        if not len(signal):
            count_in_tmp(fno_signal_found)
            continue
        else:
            #count_in_tmp(fpass_squiggle)
            junction_squiggle = np.array(signal, float)

            # outlier removal
            junction_squiggle = junction_squiggle[
                                        abs(junction_squiggle) < 3]        
        model_dic = helper.expect_squiggle_dict(seqs=candidates_for_read, 
                                                trim=trim_model,
                                                model='squiggle_r94',
                                                uniform_dwell=4)

        score_output = []
        score_trimmed = []
        score_trimmed2 = []
        cum_path = {}
        squiggle_match = {}
        element_wise_logL = {}
        output_suffix = '_c4_renorm'
        num_of_cand = len(candidates_for_read)
        
        # loop over candidate for each junction within read
        for j, candidiate in enumerate(candidates_for_read):
            candidate_squiggle = np.array(model_dic[candidiate],float)
            
            # dtw
            path , score, cum_matrix = \
                dtw_local_alignment(candidate_squiggle=candidate_squiggle, 
                                    junction_squiggle = junction_squiggle)
            
            # candidate squiggle in matched len of junction suqiggle
            squiggle_match[j] = candidate_squiggle[path[:,1] - 1, :]


            
            # renomalise
            if True:
                def likelihood_contribute(junction_squiggle,squiggle_match):    

                    diff = abs(junction_squiggle - squiggle_match[:,0])
                    z = diff/squiggle_match[:,1]
                    laplacc_b = squiggle_match[:,1]/np.sqrt(2)
                    #return 0.9189385 + z**2/2 #norm
                    #return 1.14473 + log(1+z**2) # t with df = 1
                    return np.log(2*laplacc_b) + diff/laplacc_b


                medslope, medintercept = theilslopes(y = junction_squiggle,
                                            x = squiggle_match[j][:,0])[:2]
                squiggle_match[j][:,0] = medslope *  squiggle_match[j][:,0] + medintercept
                squiggle_match[j][:,1] = np.sqrt(medslope) *  squiggle_match[j][:,1]
                candidate_squiggle[:,0] = medslope *  candidate_squiggle[:,0] + medintercept
                candidate_squiggle[:,1] = np.sqrt(medslope) *  candidate_squiggle[:,1]
                cum_path[j] = np.add.accumulate(
                            likelihood_contribute(junction_squiggle,
                                                  squiggle_match[j]))

                # # redo dtw
                if True and medslope < 1.1 and medslope > 0.9:
                    path , score, cum_matrix = \
                        dtw_local_alignment(candidate_squiggle=candidate_squiggle, 
                                        junction_squiggle = junction_squiggle)
            
            score_output.append(score)
            # candidate squiggle in matched len of junction suqiggle
            squiggle_match[j] = candidate_squiggle[path[:,1] - 1, :]
            cum_path[j] = cum_matrix[path[:, 0], path[:, 1]]            
            element_wise_logL[j] = np.append(cum_path[j][0],
                                             cum_path[j][1:] - cum_path[j][:-1])
            
            # plotting 
            if False:
                fig, axes = plt.subplots(nrows=4, figsize=(30,40))
                axes[0].plot(junction_squiggle,linewidth = 10)
                axes[0].tick_params(labelsize=40)
                            #axes[1].figure(figsize=(10,5))
                axes[1].plot(candidate_squiggle[:,0], color = "orange",linewidth =7)
                axes[1].plot(candidate_squiggle[:,0] + candidate_squiggle[:,1], ":",color = "orange",linewidth = 4)
                axes[1].plot(candidate_squiggle[:,0] - candidate_squiggle[:,1], ":",color = "orange",linewidth = 4)
                axes[1].tick_params(labelsize=40)
                axes[1].set_title("Scrappie model",fontsize=30, pad = 1)
                axes[2].plot(junction_squiggle,linewidth = 10)
                axes[2].tick_params(labelsize=40)
                #path = np.array(path[::-1])
                axes[2].plot(path[:,0]-1, candidate_squiggle[[path[:,1]-1]][:,0],'',color = "orange",linewidth = 7)
                axes[2].plot(path[:,0]-1, candidate_squiggle[[path[:,1]-1]][:,0]\
                                                + candidate_squiggle[[path[:,1]-1]][:,1],':',color = "orange",linewidth = 4)
                axes[2].plot(path[:,0]-1, candidate_squiggle[[path[:,1]-1]][:,0]\
                                                - candidate_squiggle[[path[:,1]-1]][:,1],':',color = "orange",linewidth = 4)
                axes[2].set_title(str(i)+"\nDist: {:.2f}, path length: {}, Adjusted dist: {:.2f}".format(score,len(path),score/len(path)),fontsize=40, pad = 1)
                pos = axes[3].imshow(cum_matrix, cmap='hot', interpolation='nearest',aspect='auto')
                fig.colorbar(pos,ax = axes[3])
                axes[3].plot(path[:,1], path[:,0])
                axes[3].set_title("Alignment path",fontsize=30, pad = 20)
                if read.is_reverse:
                    strand = 1
                else:
                    strand = 0
                fig.savefig("fig{}_{}.png".format('555f59a2-784b-4fbc-8392-6ff32fd5dcb4', i))

        '''
        number of points contribute to LR
        '''   
        
        #use best matched squiggle as reference
        ref_cand = squiggle_match[np.argmin(score_output)]
        out_of_sd = np.zeros(len(junction_squiggle) ,dtype = int)
        out_of_sd_ind = {}
        for j in range(num_of_cand):
            out_of_sd_ind[j] = np.zeros(len(junction_squiggle) ,dtype = int)

        
        for x in range(len(junction_squiggle)):
            for j in range(num_of_cand):
                if squiggle_match[j][x,0] - ref_cand[x,0] > ref_cand[x,1]:
                    out_of_sd[x] = 1
                    out_of_sd_ind[j][x] = 1
        
        for j in range(num_of_cand):
            score_trimmed.append(sum(out_of_sd * element_wise_logL[j]))
            score_trimmed2.append(sum(out_of_sd_ind[j] * element_wise_logL[j]))


        f = open(output_file[:-4]+output_suffix+'.tsv', "a")
        fcntl.flock(f,fcntl.LOCK_EX)

        f.write('{},{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\n'.format(
                    junction[0],
                    junction[1],
                    ','.join([str(x)+','+str(y) for x,y in candidates_pos]),
                    score_output.index(min(score_output)), 
                    read.qname,
                    score_output,
                    len(path),
                    sum(out_of_sd),
                    score_trimmed,
                    score_trimmed2,
                    [sum(x) for x in out_of_sd_ind.values()]
                            ))
        fcntl.flock(f,fcntl.LOCK_UN)
        f.close()       


'''
Functions to select junction squiggles without the requirement of transcript reference

Input:
    BED line
    Cigar string
    fast5 filename

output:
    Normalised junction squiggles
'''

def tombo_squiggle_to_basecalls(multi_fast5, AlignedSegment):
    '''
    script from tombo (https://gist.github.com/marcus1487/5cf083644143aafc770dceb213783346)
    Input:
        read_fast5: fast5 filename
    Returns:
        rsqgl_results <class>: Resquiggle result
           # useful rsqgl_results attributes:
                #   - genome_seq: clipped basecalls to model-able positions (can't get k-mers and thus expected levels for first and last few bases)
                #   - raw_signal: median normalized raw signal values (only for portion of raw signal mapped to model-able basecalls)
                #   - read_start_rel_to_raw: start of rsqgl_results.raw_signal and rsqgl_results.segs within original all_raw_signal
                #   - segs: start position for each model-able base (should be one longer than length of genome_seq to include last end point) 
    '''
    from tombo import tombo_helper, tombo_stats, resquiggle
    # extract read info
    #fast5s_f = get_fast5_file(read_fast5_fn, 'r')
    #fast5_data = h5py.File
    seq_samp_type = tombo_helper.seqSampleType('DNA', False)
    #seq_data = resquiggle.get_read_seq(fast5_data, 'Basecall_1D_000', 'BaseCalled_template', seq_samp_type, 0)
    
    if AlignedSegment.is_reverse:
        read_seq = helper.reverse_complement(AlignedSegment.seq)
    else:
        read_seq = AlignedSegment.seq

    
    seq_data = tombo_helper.sequenceData(seq=read_seq, 
                                         id=AlignedSegment.qname, 
                                         mean_q_score=np.mean(AlignedSegment.query_qualities))
    # prep tombo objects
    std_ref = tombo_stats.TomboModel(seq_samp_type=seq_samp_type)
    start_clip = std_ref.central_pos
    end_clip = std_ref.kmer_width - std_ref.central_pos - 1
    rsqgl_params = tombo_stats.load_resquiggle_parameters(seq_samp_type)

    # extract raw signal
    #all_raw_signal = tombo_helper.get_raw_read_slot(fast5_data)['Signal'][:]
    all_raw_signal = multi_fast5.get_read(AlignedSegment.qname).get_raw_data()
    # if this is a direct RNA read, flip raw signal to process from 5' to 3'
    if seq_samp_type.rev_sig:
        all_raw_signal = all_raw_signal[::-1]

    # spoof mapping read to its own basecalls (with pseudo-clipped bases in genome_location for model-able postions)
    map_results = tombo_helper.resquiggleResults(
        align_info=tombo_helper.alignInfo(ID=seq_data.id, Subgroup='BaseCalled_template', ClipStart=0, ClipEnd=0, Insertions=0,
                                        Deletions=0, Matches=len(seq_data.seq), Mismatches=0),
        genome_loc=tombo_helper.genomeLocation(Start=std_ref.central_pos, Strand='+', Chrom='NA'),
        genome_seq=seq_data.seq, raw_signal=all_raw_signal, mean_q_score=seq_data.mean_q_score)

    # align raw signal to basecalls
    try:
        rsqgl_results = resquiggle.resquiggle_read(
        map_results, std_ref, rsqgl_params, all_raw_signal=all_raw_signal)
    except:
        rsqgl_params = rsqgl_params ._replace(bandwidth=2000)
        rsqgl_results = resquiggle.resquiggle_read(
        map_results, std_ref, rsqgl_params, all_raw_signal=all_raw_signal)

    return rsqgl_results, start_clip, end_clip


def genome_to_read_pos_conversion(cigar):
    '''
    Input:
        g_pos: 0-base position within genome
        cigar: CIGAR string from BAM/SAM file
    
    Returns:
        r_pos: 0-base position within a read
    '''
    cigar_long = []
    for count, type in re.findall('(\d+)([A-Za-z])', cigar):
        cigar_long += int(count) * [type]
    r_index = -1
    g_r_mapping = []
    for i in cigar_long:
        if i in "MIS":
            r_index += 1
        if i in "MD":
            g_r_mapping.append(r_index)
        if i == "N":
            g_r_mapping.append(-1)
    return g_r_mapping


def main():
    # get command line input
    fast5_dir, output_path, alignment_file, genome_ref, \
        bandwidth, trim_model, trim_signal, \
        flank_size, window, group_filename = parse_arg()
    
    # test 
    output_path = os.path.splitext(
        os.path.basename(group_filename))[0]


    os.system("mkdir -p {}".format(output_path))
    
    #temp file output
    log_file = "{}/log.txt".format(output_path)
    
    # get fast5 filenames recursively
    fast5_paths = Path(fast5_dir).rglob('*.fast5') # iterator

    # get intron boundary position.
    fbam = pysam.AlignmentFile(alignment_file)
    fref = pysam.FastaFile(genome_ref)
    f_fetch = fbam.fetch() # reads iterator
    f_introns = fbam.find_introns(f_fetch) # dictionary
    chrID = os.path.basename(alignment_file)[:-4] # e.g 'NC_000001.11.bam' to chrID

    out_fn = "{}/{}.tsv".format(output_path,chrID)

    # junction identification (use IntervalTree for fast query)
    intron_tree = IntervalTree()
    for (begin, end), data in f_introns.items():
        intron_tree.addi(begin, end, data)

        ## built non overlapped range
    intron_tree_non_overlaps = intron_tree.copy()
    intron_tree_non_overlaps.merge_overlaps()
    
    all_candidates = []

    # start to processing the fast5 (multiread format)
    print("running process")

    from itertools import repeat
    with concurrent.futures.ProcessPoolExecutor(64) as executor:
        tqdm(executor.map(run_multifast5, fast5_paths, 
                     repeat(all_candidates),
                     repeat(alignment_file),
                     repeat(genome_ref),
                     repeat(window),
                     repeat(chrID),
                     repeat(flank_size),
                     repeat(trim_model),
                     repeat(trim_signal),
                     repeat(bandwidth),
                     repeat(out_fn),
                     repeat(group_filename)
                     ))
        

    # # log finish
    # log_fn = "{}/{}.tsv".format(output_path,chrID)
    # log_f = open(log_fn, "a")
    # fcntl.flock(log_f,fcntl.LOCK_EX)
    # log_f.write('{} complete'.format(log_fn))
    # fcntl.flock(log_f,fcntl.LOCK_UN)
    # log_f.close()   

def run_test(fast5_path , 
                    all_junctions, 
                    AlignmentFile, 
                    ref_FastaFile, 
                    window, chrID, 
                    flank_size,
                    trim_model,
                    trim_signal,
                    dtw_local_alignment,
                    output_file):
    print(fast5_path)
if __name__ == "__main__":
    main()
###############################################################################################
###############################################################################################
###############################################################################################
###############################################################################################
###############################################################################################
###############################################################################################
# test
# get alignment given genome pos

#
#all_candidate = []
#for interval in intron_tree_non_overlaps:
#    candidates = find_candidate(interval.begin, interval.end, intron_tree, 10)
#    if candidates:
#        all_candidate += candidates
#
#sum([x.data for x in all_candidate])
#[(a.get_blocks()[i-1][1], a.get_blocks()[i][0]) for i in range(1, len(a.get_blocks()))]
#
#
#
#well_supported = [x for x in f_introns.items() if x[1] > 50]
#sort_well = sorted(well_supported, key = lambda k: k[0][0])
#sorted([sort_well[i][0][0] - sort_well[i-1][0][0] for i in range(1,len(sort_well))])[1:10]