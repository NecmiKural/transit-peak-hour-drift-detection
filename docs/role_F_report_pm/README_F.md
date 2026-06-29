# Role F, Report & presentation / PM

**Owner:** Eugene · **Status:** assigned

Drop here the document(s) this role produces (any format) **and supporting
files** (assembled draft, slide deck, optional video).

**Covers in the report:** Abstract, Introduction, Conclusion; overall
assembly into Overleaf; CRediT paragraph; the slides.

**Also the assembler:** collects everyone's docs from the `role_*` folders,
merges into `../report_sections/` order, and produces the final PDF.

**Suggested file naming:** `F_<topic>_<name>.<ext>`.

## Files dropped here

Link to Overleaf Report: https://www.overleaf.com/1843283756tzhhwjncdbjp#b1eb12

Let me know if it doesn't work.


## Theory Notes:

ampm_summary_real.csv: "- ACTIONABLE: official 06:00/17:00 windows miss the real picture - e.g. Mall needs evening reinforcement ~16:00 on weekdays but ~19:00 on weekends; BusStation evening peak is sharp at 17:05 and ~48min later at weekends." - Important! Just in case this wasn't spotted before (I haven't seen the file here yet, 01_download_data.py doesn't seem to refer to it), the stop_times.txt file will help as a strong comparison. Setting the peak times for AM/PM was a *synthetic* measure, the scheduled stop times are in Hugging face:

"5. stop_times.txt – Contains the *scheduled* departure and arrival times at each stop for every trip (using trip_id, arrival_time, departure_time, stop_id, stop_sequence). – Enables analysis of headways, dwell times, and temporal patterns."

We might have to split the analysis into two hierarchies: Operational + Conceptual. 

The overall aim: demonstrate GTFS tables used for transit scheduling fail to map real passenger demand.
The core variables here are thus 1. how good the schedule is under predictable ("controlled variable") passenger demand -> (Operational, extrinsic), 
and 2. how predictable passenger demand really is -> (Conceptual, intrinsic). 
And, as should be obvious, general scheduling efficacy is dependent on real passenger demand but not the other way around.

Operational branch: measures the variance between a static schedule operation "T" against a boarding volume change (stream "S"). 
Then we could isolate the stream S to something like "clear-weather weekDAYS" and evaluate whether shifts occur with respect to T (look at weekend shift min in ampm real csv, use that analysis with stop_times.txt as the official / real arrival data)
If |T-S|>>0 (huge discrepancy), then the GTFS is already bad from the get-go; we can already see from ampm_summary_real.csv and
ampm_47568123.png Shopping Mall how different weekday, and weekend are from the official time. 
But the "official" schedule column in the ampm csv (please correct me if I have this mistaken) is synthetic. 
We clearly see a huge discrepancy on weekend vs. official and a noticeable one on weekday vs. official. 
This is a great example of what to look out for when we test the "Operational efficacy" of stop_times.txt against the boarding data. 
As stated above, efficacy would be dependent on the concept drift of passenger demand, so to be rigorous with testing we could test with the 
aforementioned "clear weather weekDAYs" / "clear weather weekENDs" as control variables. 

Conceptual branch: Standard concept drift. This is intrinsic to the stream, since we can see that even with the poor synthetic official schedule of 
the Mall we still detected no concept drifts (we did however detect differences between regimes/categories but that's an extra point for now). 
Therefore, we would need to compare this data to things like weather as covariates, which real passenger demand COULD be dependent on.
Hence showing that weather changes induce concept drifts in the boarding stream S that even a calibrated schedule T could not predict.
To satisfy this last sentence, and since T ought to be dependent on S, we would look for T~S being altered when weather induces a change on S.

From what I can see we now need the stop_times.txt data and weather data, even if the weather data doesn't correlate to drifts we still want external data +
this would even rigorously show that something that would commonly cause drifts doesn't in this case (I'm assuming at least, since no intrinsic drift was found so far).
Thus, IF stop_times misaligns with the boarding streams despite there not being any drifts, weather correlation, etc. then we have strongly proved the poor behavior of schedule T.
Again, assuming the real schedule behaves as bad as our set times for AM/PM (If the "official" schedule was taken from a data source then let me know, because in that case we basically would have done the hardest part already).

### A nice elaboration by Gemini:

How to frame this: You do not prove that weather alters the schedule. You prove that weather alters the passengers, and because the schedule cannot alter to match them, the system shatters.

The Conundrum: What if the EDA / ADWIN found zero weather drift?You asked: "Now, in the EDA we spotted no concept drifts, does this mean that we wouldnt be able to find some weather pattern causing a concept drift if no drift was found? Or we could still find weather patterns being correlated with the microchanges in the stream..."

If your CapyMOA ADWIN algorithm processed the stream and returned zero Hoeffding bound violations for weather, this is not a failure of your project. In data science, a verified "null" result is just as mathematically powerful as a positive one. Here is exactly how you handle this in the report without losing any academic rigor:

1. The Inelasticity of Human Demand (The Null Hypothesis)
If ADWIN found zero drifts during rain, it mathematically proves that passenger behavior at that specific spatial node $v$ is inelastic to meteorological covariates.
People who work at the Shopping Mall still get off work at exactly 15:57, regardless of whether it is sunny or pouring rain.
Because the EWMA low-pass filter ($\delta_{\text{min\_sustain}} = 4$ intervals) intentionally discards high-frequency noise, minor 5-minute micro-fluctuations caused by people running out of the rain are correctly filtered out as stochastic noise, not structural concept drift.

2. How Zero Drift Supercharges Problem 1 (Operational Divergence)
Finding zero weather drift actually makes your first problem (Operational Divergence) infinitely more devastating.
If human demand ($S$) is so ridiculously stable that even a severe storm cannot induce a concept drift, it means $S$ is a perfectly predictable, stationary target during weekdays.Therefore, if $S$ is perfectly predictable, and the transit authority's schedule ($\mathcal{T}$) still misses the true peak by 63 minutes ($\Delta = 63$), you have proven structural incompetence.

The Argument for your Paper:"Our stream evaluation proves that empirical demand ($S$) at the commercial node is highly stable, resisting temporal concept drift even under stochastic meteorological variance. However, despite this stationary, predictable demand behavior, evaluating $S$ against the granular \texttt{stop_times.txt} matrix ($\mathcal{T}$) reveals a massive baseline operational divergence. The operator has failed to map their supply vectors to a perfectly stable target, proving that GTFS failures in this network are caused by structural spatial misalignment rather than unpredicted environmental volatility."

3. Searching for Micro-Changes (Optional Optimization)
If you want to find weather correlations to prove the streaming algorithm's worth, you have two mechanical options:
Lower the ADWIN Tolerance: If your $\epsilon_{\text{Hoeffding}}$ or ADWIN_DELTA parameter is set too strictly (e.g., $0.002$), it requires a massive behavioral shift to trigger. Relaxing the threshold might expose smaller, valid drifts.
Change the Spatial Node: The Shopping Mall might be weather-resistant, but an outdoor node (like a park or open-air market) will likely show massive weather-induced concept drift. Checking a different $v \in V$ might immediately yield the weather drift you are looking for.


