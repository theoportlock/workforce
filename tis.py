import splitter
import basechanger
import comb
import inreader
import outreader
import addnewelement

nerv = [0]*3
newnerv = [0]*8

text = inreader.a("input.txt")

for c in text:
  for e in basechanger.a(addnewelement.a(nerv,c)):
    print(splitter.a(addnewelement.a(newnerv,e)))
