import struct, math, os, zipfile, datetime as dt

OUT = os.path.join(os.path.dirname(__file__), "testfiles")
os.makedirs(OUT, exist_ok=True)
FIT_EPOCH = 631065600


def fit_file(chunks):
    body = b"".join(chunks)
    hdr = struct.pack("<BBHI4sH", 14, 0x10, 2000, len(body), b".FIT", 0)
    return hdr + body + struct.pack("<H", 0)


def definition(local, gmsg, fields):
    b = struct.pack("<BBBHB", 0x40 | local, 0, 0, gmsg, len(fields))
    for num, size, btype in fields:
        b += struct.pack("<BBB", num, size, btype)
    return b


def bike(start_unix, minutes=62):
    t0 = start_unix - FIT_EPOCH
    chunks = [definition(0, 20, [(253, 4, 0x86), (3, 1, 0x02), (7, 2, 0x84), (4, 1, 0x02), (5, 4, 0x86)])]
    n = minutes * 60
    dist = 0
    pw = []
    for i in range(n):
        m = i / 60
        if m < 10:
            p = 110 + 3 * m
        elif 10 <= m < 22 or 27 <= m < 39:
            p = 172 + 6 * math.sin(i / 7)
        elif m >= 52:
            p = 120 - (m - 52) * 2
        else:
            p = 112
        p = int(max(0, p))
        pw.append(p)
        hr = int(95 + 0.55 * p + min(m, 20) * 0.6)
        dist += 8.2
        chunks.append(struct.pack("<BIBHBI", 0x00, t0 + i, hr, p, 85, int(dist * 100)))
    avgp = round(sum(pw) / n)
    chunks.append(definition(1, 18, [(253, 4, 0x86), (2, 4, 0x86), (5, 1, 0x00), (6, 1, 0x00), (7, 4, 0x86), (8, 4, 0x86),
                                     (9, 4, 0x86), (16, 1, 0x02), (17, 1, 0x02), (20, 2, 0x84), (21, 2, 0x84), (22, 2, 0x84), (34, 2, 0x84)]))
    chunks.append(struct.pack("<BIIBBIIIBBHHHH", 0x01, t0 + n, t0, 2, 6, n * 1000, n * 1000, int(dist * 100), 140, 163, avgp, 231, 0, 168))
    return fit_file(chunks)


def swim(start_unix, minutes=45):
    t0 = start_unix - FIT_EPOCH
    chunks = [definition(1, 18, [(253, 4, 0x86), (2, 4, 0x86), (5, 1, 0x00), (6, 1, 0x00), (7, 4, 0x86), (8, 4, 0x86), (9, 4, 0x86), (16, 1, 0x02)])]
    chunks.append(struct.pack("<BIIBBIIIB", 0x01, t0 + minutes * 60, t0, 5, 17, minutes * 60000, minutes * 60000, 180000, 128))
    return fit_file(chunks)


def tcx(start_iso, minutes=40):
    pts = []
    base = dt.datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    for i in range(0, minutes * 60, 5):
        t = (base + dt.timedelta(seconds=i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        pts.append(f"<Trackpoint><Time>{t}</Time><DistanceMeters>{i * 7.5:.0f}</DistanceMeters><HeartRateBpm><Value>{140 + (i // 60) % 15}</Value></HeartRateBpm>"
                   f"<Extensions><ns3:TPX xmlns:ns3='http://www.garmin.com/xmlschemas/ActivityExtension/v2'><ns3:Watts>{180 + (i // 30) % 40}</ns3:Watts></ns3:TPX></Extensions></Trackpoint>")
    return (f"<?xml version='1.0'?><TrainingCenterDatabase xmlns='http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2'><Activities>"
            f"<Activity Sport='Biking'><Id>{start_iso}</Id><Lap StartTime='{start_iso}'><TotalTimeSeconds>{minutes * 60}</TotalTimeSeconds>"
            f"<DistanceMeters>{minutes * 60 * 7.5:.0f}</DistanceMeters><Calories>600</Calories><Track>{''.join(pts)}</Track></Lap></Activity></Activities></TrainingCenterDatabase>")


def gpx(start_iso, minutes=30):
    base = dt.datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    pts = []
    for i in range(0, minutes * 60, 10):
        t = (base + dt.timedelta(seconds=i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        pts.append(f"<trkpt lat='{50.11 + i * 1e-5:.6f}' lon='{8.68 + i * 1e-5:.6f}'><time>{t}</time><extensions><gpxtpx:TrackPointExtension xmlns:gpxtpx='http://www.garmin.com/xmlschemas/TrackPointExtension/v1'><gpxtpx:hr>{150 + i // 120 % 10}</gpxtpx:hr></gpxtpx:TrackPointExtension></extensions></trkpt>")
    return f"<?xml version='1.0'?><gpx version='1.1' xmlns='http://www.topografix.com/GPX/1/1'><trk><type>running</type><trkseg>{''.join(pts)}</trkseg></trk></gpx>"


d = lambda y, mo, da, h, mi: int(dt.datetime(y, mo, da, h, mi, tzinfo=dt.timezone.utc).timestamp())
open(f"{OUT}/spinning_di.fit", "wb").write(bike(d(2026, 10, 13, 16, 30)))
open(f"{OUT}/schwimmen_do.fit", "wb").write(swim(d(2026, 10, 15, 17, 0)))
open(f"{OUT}/rolle_fr.tcx", "w").write(tcx("2026-10-16T16:00:00Z"))
open(f"{OUT}/lauf.gpx", "w").write(gpx("2026-10-18T08:00:00Z"))
with zipfile.ZipFile(f"{OUT}/garmin_export.zip", "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("12345_ACTIVITY.fit", bike(d(2026, 10, 17, 9, 0), 95))
print(os.listdir(OUT))
