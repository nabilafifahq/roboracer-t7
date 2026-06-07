import re
p='main_globaltraj.py'; s=open(p).read()
s=re.sub(r'pkg_resources\.require\(dependencies\)','pass',s)
s=re.sub(r'file_paths\["track_name"\]\s*=.*','file_paths["track_name"] = "hallway"',s)
s=re.sub(r'^opt_type\s*=.*',"opt_type = 'mincurv'",s,flags=re.M)
open(p,'w').write(s)
