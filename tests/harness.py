import sys, os, types, logging
os.environ.setdefault('REQUIRE_AUTH','0')
# Resolve everything from this file's location so the suite runs from ANY working directory.
_HERE = os.path.dirname(os.path.abspath(__file__))
root = REPO_ROOT = os.path.dirname(_HERE)
os.chdir(root)                       # several tests use repo-root-relative paths (./api, ./telegram-bot)
sys.path.insert(0, os.path.join(_HERE, 'stubs'))
sys.path.insert(0, root+'/api'); sys.path.insert(0, root+'/api/_lib')
logging.disable(logging.CRITICAL)
import pokeapi_manager
DEX={"charmander":(4,["fire"],["blaze","solar-power"],[39,52,43,60,50,65]),
     "squirtle":(7,["water"],["torrent","rain-dish"],[44,48,65,50,64,43]),
     "pidgey":(16,["normal","flying"],["keen-eye","tangled-feet"],[40,45,40,35,35,56]),
     "rattata":(19,["normal"],["run-away","guts"],[30,56,35,25,35,72]),
     "gyarados":(130,["water","flying"],["intimidate","moxie"],[95,125,79,60,100,81]),
     "pikachu":(25,["electric"],["static","lightning-rod"],[35,55,40,50,50,90]),
     "abra":(63,["psychic"],["synchronize"],[25,20,15,105,55,90]),
     "zubat":(41,["poison","flying"],["inner-focus"],[40,45,35,30,40,55]),
     "sandshrew":(27,["ground"],["sand-veil"],[50,75,85,20,30,40]),
     "bulbasaur":(1,["grass","poison"],["overgrow"],[45,49,49,65,65,45]),
     "geodude":(74,["rock","ground"],["sturdy"],[40,80,100,30,30,20]),
     "onix":(95,["rock","ground"],["sturdy"],[35,45,160,30,45,70]),
     "chansey":(113,["normal"],["natural-cure"],[250,5,5,35,105,50]),
     "pidgeot":(18,["normal","flying"],["keen-eye"],[83,80,75,70,70,101]),
     "caterpie":(10,["bug"],["shield-dust"],[45,30,35,20,20,45]),
     "alakazam":(65,["psychic"],["synchronize"],[55,50,45,135,95,120]),
    }
def fake_get(name):
    n=name.lower()
    d=DEX.get(n, (100,["normal"],["run-away"],[50]*6))
    hp,at,df,sa,sd,sp=d[3]
    return {"id":d[0],"name":n,"types":d[1],"abilities":d[2],
            "base_stats":{"hp":hp,"attack":at,"defense":df,"sp_atk":sa,"sp_def":sd,"speed":sp},
            "moves":["tackle","scratch","ember","water-gun"],"image":"x","catch_rate":45}
pokeapi_manager.pokeapi.get_pokemon=fake_get
