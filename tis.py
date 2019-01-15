import splitter
import unpacker
import basechanger
import comb3
import inreader
import outreader
import addnewelement

nerv = [0]*1
newnerv = [0]*5
text = inreader.a("input.txt")

print('text = {0}\n'.format(text))

for c in text:
  nerv = addnewelement.a(nerv,c)
  #print ('nerv			{0}'.format(nerv))
  #print ('then changed base	{0}'.format(basechanger(nerv)))
  for e in basechanger.a(nerv):
    newnerv = addnewelement.a(newnerv,e)
    split = splitter.a(newnerv)
  #print('	splitcomb	{0}'.format(splitter.a(unpacker.a(comb3.a(split)))))
  #print ('	newnerv		{0}'.format(newnerv))
  #print ('	split		{0}'.format(split))
  #print ('	comb		{0}'.format(combinations(split)))
  #print ('	testsplit	{0}'.format(splitter(combinations(split),split)))
  #print ('\n')
